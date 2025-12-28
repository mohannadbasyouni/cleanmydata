"""FastAPI application for CleanMyData - HTTP API wrapper around the cleaning pipeline."""

import io
import tempfile
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from ddtrace import config as dd_config
from ddtrace import patch, tracer
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from cleanmydata.ai.gemini import GeminiClient
from cleanmydata.clean import _determine_dataset_kind, clean_data
from cleanmydata.config import CleaningConfig
from cleanmydata.exceptions import DataLoadError
from cleanmydata.models import Suggestion

# -----------------------------------------------------------------------------
# Datadog APM Configuration
# -----------------------------------------------------------------------------
# Required environment variables for Datadog APM:
# - DD_SERVICE: Service name (default: cleanmydata)
# - DD_ENV: Environment (e.g., dev, staging, prod)
# - DD_VERSION: Application version (e.g., 0.1.0)
# - DD_AGENT_HOST: Datadog Agent hostname (default: localhost)
# - DD_TRACE_AGENT_PORT: Datadog Agent port (default: 8126)

# Configure service name and auto-instrumentation
dd_config.service = "cleanmydata"

# Enable FastAPI auto-instrumentation
patch(fastapi=True)

# -----------------------------------------------------------------------------
# Application Setup
# -----------------------------------------------------------------------------

app = FastAPI(
    title="CleanMyData API",
    description="AI-assisted data cleaning with full observability",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------


class JobStatus(str, Enum):
    """Status of a cleaning job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CleaningOptions(BaseModel):
    """Options for the cleaning pipeline."""

    outliers: str = Field(
        default="cap", description="Outlier handling method: 'cap', 'remove', or 'none'"
    )
    normalize_cols: bool = Field(default=True, description="Normalize column names")
    clean_text: bool = Field(default=True, description="Clean text columns")
    auto_outlier_detect: bool = Field(
        default=True, description="Auto-detect outlier method per column"
    )


class JobSubmitResponse(BaseModel):
    """Response when a cleaning job is submitted."""

    job_id: str
    status: JobStatus
    message: str


class CleaningSummary(BaseModel):
    """Summary statistics from the cleaning operation."""

    rows: int = 0
    columns: int = 0
    duplicates_removed: int = 0
    outliers_handled: int = 0
    missing_filled: int = 0
    columns_standardized: int = 0
    text_unconverted: int = 0
    duration: str = ""


class SuggestionModel(BaseModel):
    """Structured AI suggestion."""

    category: str
    severity: str
    message: str
    column: str | None = None
    evidence: dict | None = None


class JobStatusResponse(BaseModel):
    """Response for job status queries."""

    job_id: str
    status: JobStatus
    created_at: str
    completed_at: str | None = None
    original_filename: str | None = None
    summary: CleaningSummary | None = None
    download_url: str | None = None
    ai_suggestions: list[SuggestionModel] = Field(default_factory=list)
    error: str | None = None


# -----------------------------------------------------------------------------
# In-Memory Job Storage (for hackathon - replace with Redis/DB in production)
# -----------------------------------------------------------------------------


class JobStore:
    """Simple in-memory job storage."""

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._temp_dir = tempfile.mkdtemp(prefix="cleanmydata_")

    def create_job(self, original_filename: str) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = {
            "status": JobStatus.PENDING,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "completed_at": None,
            "original_filename": original_filename,
            "summary": None,
            "output_path": None,
            "ai_suggestions": [],
            "error": None,
        }
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> None:
        """Update job fields."""
        if job_id in self._jobs:
            self._jobs[job_id].update(kwargs)

    def get_temp_path(self, job_id: str, suffix: str = ".csv") -> Path:
        """Get a temporary file path for storing output."""
        return Path(self._temp_dir) / f"{job_id}_cleaned{suffix}"


# Global job store instance
job_store = JobStore()


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def read_uploaded_file(file: UploadFile) -> pd.DataFrame:
    """Read an uploaded file into a DataFrame."""
    with tracer.trace("cleaning.file_parse", service="cleanmydata") as span:
        filename = file.filename or "unknown"
        suffix = Path(filename).suffix.lower()

        span.set_tag("filename", filename)
        span.set_tag("file_format", suffix)

        if suffix not in (".csv", ".xlsx", ".xlsm"):
            span.set_tag("error", True)
            raise DataLoadError(
                f"Unsupported file format: {suffix}. Supported formats: .csv, .xlsx, .xlsm"
            )

        content = file.file.read()
        span.set_tag("file_size_bytes", len(content))

        if suffix == ".csv":
            try:
                df = pd.read_csv(io.BytesIO(content))
                span.set_tag("rows", len(df))
                span.set_tag("columns", len(df.columns))
                return df
            except pd.errors.EmptyDataError as e:
                span.set_tag("error", True)
                raise DataLoadError("The uploaded CSV file is empty or invalid") from e
            except pd.errors.ParserError as e:
                span.set_tag("error", True)
                raise DataLoadError(f"Failed to parse CSV file: {e}") from e
        else:
            # Excel files
            try:
                import openpyxl  # noqa: F401
            except ImportError as e:
                span.set_tag("error", True)
                raise DataLoadError(
                    "Excel support is not installed on the server. Please upload a CSV file."
                ) from e
            try:
                df = pd.read_excel(io.BytesIO(content))
                span.set_tag("rows", len(df))
                span.set_tag("columns", len(df.columns))
                return df
            except Exception as e:
                span.set_tag("error", True)
                raise DataLoadError(f"Failed to read Excel file: {e}") from e


def run_cleaning_pipeline(job_id: str, df: pd.DataFrame, options: CleaningOptions) -> None:
    """Run the cleaning pipeline as a background task."""
    with tracer.trace("cleaning.pipeline", service="cleanmydata") as span:
        span.set_tag("job_id", job_id)
        span.set_tag("rows_before", len(df))
        span.set_tag("columns", len(df.columns))

        job_store.update_job(job_id, status=JobStatus.PROCESSING)

        try:
            # Build config from options
            config = CleaningConfig(
                outliers=options.outliers if options.outliers != "none" else None,
                normalize_cols=options.normalize_cols,
                clean_text=options.clean_text,
                auto_outlier_detect=options.auto_outlier_detect,
                verbose=False,
            )

            # Run the cleaning pipeline
            dataset_name = job_store.get_job(job_id)["original_filename"]
            cleaned_df, summary = clean_data(
                df,
                outliers=config.outliers,
                normalize_cols=config.normalize_cols,
                clean_text=config.clean_text,
                auto_outlier_detect=config.auto_outlier_detect,
                verbose=config.verbose,
                log=False,
                dataset_name=dataset_name,
            )

            span.set_tag("rows_after", len(cleaned_df))
            span.set_tag("duplicates_removed", summary.get("duplicates_removed", 0))
            span.set_tag("outliers_handled", summary.get("outliers_handled", 0))
            span.set_tag("missing_filled", summary.get("missing_filled", 0))

            # Save cleaned data
            with tracer.trace("cleaning.save_output", service="cleanmydata") as save_span:
                save_span.set_tag("job_id", job_id)
                output_path = job_store.get_temp_path(job_id, suffix=".csv")
                cleaned_df.to_csv(output_path, index=False)
                save_span.set_tag("output_path", str(output_path))

            dataset_kind = _determine_dataset_kind(dataset_name)
            gemini = GeminiClient()
            ai_suggestions: list[Suggestion] = gemini.analyze_data_quality(
                cleaned_df, summary, dataset_kind=dataset_kind
            )

            # Update job with results
            job_store.update_job(
                job_id,
                status=JobStatus.COMPLETED,
                completed_at=datetime.utcnow().isoformat() + "Z",
                summary=CleaningSummary(**summary),
                output_path=str(output_path),
                ai_suggestions=[s.to_dict() for s in ai_suggestions],
            )

        except Exception as e:
            span.set_tag("error", True)
            span.set_tag("error.message", str(e))
            job_store.update_job(
                job_id,
                status=JobStatus.FAILED,
                completed_at=datetime.utcnow().isoformat() + "Z",
                error=str(e),
            )


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "service": "CleanMyData API",
        "version": "0.1.0",
        "status": "healthy",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/clean", response_model=JobSubmitResponse, tags=["Cleaning"])
async def submit_cleaning_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV or Excel file to clean"),
    outliers: str = "cap",
    normalize_cols: bool = True,
    clean_text: bool = True,
    auto_outlier_detect: bool = True,
):
    """
    Submit a data file for cleaning.

    Accepts a CSV or Excel file and starts an asynchronous cleaning job.
    Returns a job_id that can be used to check the status and retrieve results.

    **Supported file formats:** .csv, .xlsx, .xlsm

    **Cleaning options:**
    - `outliers`: Method for handling outliers ('cap', 'remove', or 'none')
    - `normalize_cols`: Normalize column names to snake_case
    - `clean_text`: Clean and normalize text columns
    - `auto_outlier_detect`: Auto-select outlier detection method per column
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Read the uploaded file
    try:
        df = read_uploaded_file(file)
    except DataLoadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}") from e

    # Validate dataframe
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file contains no data")

    # Create job
    job_id = job_store.create_job(file.filename)

    # Build options
    options = CleaningOptions(
        outliers=outliers,
        normalize_cols=normalize_cols,
        clean_text=clean_text,
        auto_outlier_detect=auto_outlier_detect,
    )

    # Start background processing
    background_tasks.add_task(run_cleaning_pipeline, job_id, df, options)

    return JobSubmitResponse(
        job_id=job_id,
        status=JobStatus.PROCESSING,
        message="Cleaning job submitted successfully. Use GET /clean/{job_id} to check status.",
    )


@app.get("/clean/{job_id}", response_model=JobStatusResponse, tags=["Cleaning"])
async def get_job_status(job_id: str):
    """
    Get the status and results of a cleaning job.

    Returns the current status of the job, and if completed, includes:
    - Summary statistics of the cleaning operation
    - Download URL for the cleaned file
    - AI-generated suggestions (when available)
    """
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    # Build download URL if completed
    download_url = None
    if job["status"] == JobStatus.COMPLETED and job["output_path"]:
        download_url = f"/clean/{job_id}/download"

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
        original_filename=job["original_filename"],
        summary=job["summary"],
        download_url=download_url,
        ai_suggestions=job["ai_suggestions"],
        error=job["error"],
    )


@app.get("/clean/{job_id}/download", tags=["Cleaning"])
async def download_cleaned_file(job_id: str):
    """
    Download the cleaned file for a completed job.

    Returns the cleaned CSV file. Only available for completed jobs.
    """
    job = job_store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job["status"] != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job['status']}",
        )

    if not job["output_path"]:
        raise HTTPException(status_code=500, detail="Output file not found")

    output_path = Path(job["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="Output file has been deleted")

    # Generate download filename
    original = job["original_filename"] or "data"
    original_stem = Path(original).stem
    download_name = f"{original_stem}_cleaned.csv"

    return FileResponse(
        path=output_path,
        filename=download_name,
        media_type="text/csv",
    )


# -----------------------------------------------------------------------------
# Entry point for running with uvicorn
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
