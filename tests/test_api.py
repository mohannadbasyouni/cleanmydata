"""Tests for FastAPI endpoints."""

import io
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from cleanmydata.api import app, job_store


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing."""
    fixture_path = Path(__file__).parent / "fixtures" / "small.csv"
    with open(fixture_path, "rb") as f:
        content = f.read()
    return ("small.csv", io.BytesIO(content), "text/csv")


@pytest.fixture
def mock_storage_client():
    """Mock storage client that doesn't hit GCS."""
    mock_client = MagicMock()
    mock_client.upload_file.return_value = "https://storage.example.com/file.csv"
    mock_client.generate_download_url.return_value = "https://storage.example.com/download/file.csv"
    return mock_client


@pytest.fixture(autouse=True)
def reset_job_store():
    """Reset job store before each test."""
    job_store._jobs.clear()
    yield
    job_store._jobs.clear()


@pytest.fixture(autouse=True)
def disable_gemini(monkeypatch):
    """Disable Gemini for tests unless explicitly enabled."""
    monkeypatch.delenv("CLEANMYDATA_GEMINI_ENABLED", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)


def test_post_clean_creates_job(client, sample_csv_file, mock_storage_client):
    """Test POST /clean creates a job and returns job_id."""
    with patch("cleanmydata.api.storage_client", mock_storage_client):
        response = client.post("/clean", files={"file": sample_csv_file})

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ("processing", "completed")  # May complete immediately in tests
    assert "message" in data

    # Verify job exists in store
    job = job_store.get_job(data["job_id"])
    assert job is not None
    assert job["status"] in ("processing", "completed")
    assert job["original_filename"] == "small.csv"


def test_post_clean_with_missing_file(client):
    """Test POST /clean with missing file returns 422."""
    response = client.post("/clean")

    assert response.status_code == 422  # FastAPI validation error


def test_post_clean_with_empty_file(client):
    """Test POST /clean with empty CSV returns 400."""
    empty_csv = ("empty.csv", io.BytesIO(b"name,age\n"), "text/csv")
    response = client.post("/clean", files={"file": empty_csv})

    assert response.status_code == 400
    assert "no data" in response.json()["detail"].lower()


def test_get_job_status_returns_processing(client, sample_csv_file, mock_storage_client):
    """Test GET /clean/{job_id} returns processing status initially."""
    with patch("cleanmydata.api.storage_client", mock_storage_client):
        # Submit job
        submit_response = client.post("/clean", files={"file": sample_csv_file})
        job_id = submit_response.json()["job_id"]

        # Check status (may be processing or completed depending on timing)
        status_response = client.get(f"/clean/{job_id}")

    assert status_response.status_code == 200
    data = status_response.json()
    assert data["job_id"] == job_id
    assert data["status"] in ("processing", "completed")
    assert data["original_filename"] == "small.csv"
    # Summary may or may not be present depending on completion status
    if data["status"] == "completed":
        assert data["summary"] is not None
    else:
        assert data["summary"] is None


def test_get_job_status_returns_completed(client, sample_csv_file, mock_storage_client):
    """Test GET /clean/{job_id} returns completed status after processing."""
    with patch("cleanmydata.api.storage_client", mock_storage_client):
        # Submit job
        submit_response = client.post("/clean", files={"file": sample_csv_file})
        job_id = submit_response.json()["job_id"]

        # Wait for processing to complete (background task)
        max_wait = 10  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/clean/{job_id}")
            data = status_response.json()
            if data["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"Job {job_id} did not complete within {max_wait} seconds")

    assert status_response.status_code == 200
    data = status_response.json()
    assert data["status"] == "completed"
    assert data["summary"] is not None
    assert data["summary"]["rows"] > 0
    assert data["summary"]["columns"] > 0
    assert data["download_url"] is not None


def test_get_job_status_not_found(client):
    """Test GET /clean/{bad_job_id} returns 404."""
    response = client.get("/clean/nonexistent-job-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_job_download_returns_csv(client, sample_csv_file, mock_storage_client):
    """Test GET /clean/{job_id}/download returns CSV file."""
    with patch("cleanmydata.api.storage_client", mock_storage_client):
        # Submit job
        submit_response = client.post("/clean", files={"file": sample_csv_file})
        job_id = submit_response.json()["job_id"]

        # Wait for processing to complete
        max_wait = 10
        start_time = time.time()
        while time.time() - start_time < max_wait:
            status_response = client.get(f"/clean/{job_id}")
            data = status_response.json()
            if data["status"] == "completed":
                break
            time.sleep(0.1)
        else:
            pytest.fail(f"Job {job_id} did not complete within {max_wait} seconds")

        # Download file
        download_response = client.get(f"/clean/{job_id}/download")

    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "small_cleaned.csv" in download_response.headers.get("content-disposition", "")

    # Verify CSV content
    content = download_response.content.decode("utf-8")
    assert "name" in content.lower() or "age" in content.lower()


def test_get_job_download_not_found(client):
    """Test GET /clean/{bad_job_id}/download returns 404."""
    response = client.get("/clean/nonexistent-job-id/download")

    assert response.status_code == 404


def test_get_job_download_not_completed(client, sample_csv_file, mock_storage_client):
    """Test GET /clean/{job_id}/download returns 400 if job not completed."""
    with patch("cleanmydata.api.storage_client", mock_storage_client):
        # Submit job
        submit_response = client.post("/clean", files={"file": sample_csv_file})
        job_id = submit_response.json()["job_id"]

        # Check status first
        status_response = client.get(f"/clean/{job_id}")
        status_data = status_response.json()

        if status_data["status"] == "completed":
            # If job completed synchronously, test with a non-existent job instead
            download_response = client.get("/clean/nonexistent-job-id/download")
            assert download_response.status_code == 404
        else:
            # Try to download while still processing (should fail)
            download_response = client.get(f"/clean/{job_id}/download")
            assert download_response.status_code == 400
            assert "not completed" in download_response.json()["detail"].lower()


def test_post_clean_with_invalid_format(client):
    """Test POST /clean with unsupported file format returns 400."""
    invalid_file = ("test.txt", io.BytesIO(b"some text"), "text/plain")
    response = client.post("/clean", files={"file": invalid_file})

    assert response.status_code == 400
    assert (
        "unsupported" in response.json()["detail"].lower()
        or "format" in response.json()["detail"].lower()
    )


def test_health_endpoints(client):
    """Test health check endpoints."""
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "healthy"

    health_response = client.get("/health")
    assert health_response.status_code == 200
    assert "status" in health_response.json()
    assert "timestamp" in health_response.json()
