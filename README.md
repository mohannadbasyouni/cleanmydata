## Work In Progress...

## Datadog APM Configuration

The CleanMyData API includes built-in Datadog APM tracing for full observability of data cleaning operations.

### Required Environment Variables

Configure the following environment variables to enable Datadog APM:

```bash
# Service identification
export DD_SERVICE=cleanmydata           # Service name (default: cleanmydata)
export DD_ENV=production                # Environment (e.g., dev, staging, prod)
export DD_VERSION=0.1.0                 # Application version

# Datadog Agent connection
export DD_AGENT_HOST=localhost          # Datadog Agent hostname (default: localhost)
export DD_TRACE_AGENT_PORT=8126         # Datadog Agent APM port (default: 8126)

# Optional: Enable debug logging for troubleshooting
export DD_TRACE_DEBUG=false             # Set to true for verbose trace logging
```

### Running the API with APM

```bash
# Install with API dependencies (includes ddtrace)
pip install -e ".[api]"

# Set environment variables
export DD_SERVICE=cleanmydata
export DD_ENV=dev
export DD_AGENT_HOST=localhost

# Run the API server
python -m cleanmydata.api

# Or use uvicorn directly
uvicorn cleanmydata.api:app --host 0.0.0.0 --port 8000
```

### What Gets Traced

The instrumentation automatically traces:

- **HTTP Requests**: All FastAPI endpoints with request/response details
- **Data Pipeline**: Full cleaning pipeline execution with timing
- **File Operations**: CSV/Excel parsing with file metadata
- **Cleaning Steps**: Individual operations (deduplication, outliers, missing values, etc.)

Each trace includes relevant tags:
- `job_id`: Unique identifier for the cleaning job
- `filename`: Original uploaded filename
- `rows_before` / `rows_after`: Dataset size tracking
- `duplicates_removed`, `outliers_handled`, `missing_filled`: Operation statistics

### Log and Trace Correlation

Logs automatically include trace correlation fields when a trace is active:
- `dd.trace_id`: Datadog trace ID for correlation
- `dd.span_id`: Current span ID
- `dd.service`: Service name

This allows seamless correlation between logs and traces in the Datadog UI.
