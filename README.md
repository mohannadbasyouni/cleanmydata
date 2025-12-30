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

## Cloud Run Deployment

The CleanMyData API uses IAM-only signing for GCS signed URLs, which is the recommended production approach for Cloud Run deployments. This eliminates the need for service account JSON key files.

### GCS Storage Configuration

**Required Environment Variables:**
```bash
export CLEANMYDATA_STORAGE_BACKEND=gcs
export CLEANMYDATA_GCS_BUCKET=your-bucket-name
export CLEANMYDATA_GCS_SIGNER_EMAIL=your-service-account@project.iam.gserviceaccount.com  # Optional: auto-detected from runtime identity
export CLEANMYDATA_SIGNED_URL_TTL_SECONDS=3600  # Optional: default is 3600 seconds
```

**IAM Requirements:**

1. **Service Account**: Configure Cloud Run to run as a dedicated service account:
   ```bash
   gcloud run services update cleanmydata \
     --service-account=cleanmydata-sa@PROJECT_ID.iam.gserviceaccount.com \
     --region=us-central1
   ```

2. **Required IAM Role**: The service account needs the `roles/iam.serviceAccountTokenCreator` role to sign URLs:
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:cleanmydata-sa@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountTokenCreator"
   ```

3. **Required API**: Enable the IAM Credentials API:
   ```bash
   gcloud services enable iamcredentials.googleapis.com
   ```

4. **GCS Permissions**: The service account needs appropriate GCS bucket permissions:
   ```bash
   gsutil iam ch serviceAccount:cleanmydata-sa@PROJECT_ID.iam.gserviceaccount.com:objectCreator,objectViewer gs://your-bucket-name
   ```

**How It Works:**

- The signing process uses the IAM Credentials API (`SignBlob`) instead of private keys
- The service account email is automatically detected from the runtime identity (Cloud Run metadata server)
- No JSON key files or `GOOGLE_APPLICATION_CREDENTIALS` environment variable required
- Local development can use Application Default Credentials (`gcloud auth application-default login`) without key files

**Error Handling:**

If signing fails, you'll see clear error messages indicating:
- Missing `roles/iam.serviceAccountTokenCreator` role
- IAM Credentials API not enabled
- Service account email not found

Check application logs for detailed error information.

## Production Status

The IAM-only signing implementation is verified and running in production on Cloud Run:

- ✅ **IAM-only signing is live**: GCS signed URLs use IAM Credentials API (`SignBlob`) exclusively
- ✅ **No service account keys**: JSON key files are not used or supported; all signing uses runtime identity
- ✅ **Production verified**: Both upload (`POST /clean`) and download (`GET /clean/{job_id}/download`) endpoints tested successfully
- ✅ **Cloud Run ready**: Service account email auto-detected from runtime identity; no manual key management required
- ✅ **Zero keyfile dependencies**: `GOOGLE_APPLICATION_CREDENTIALS` is not required or expected to point to a JSON file
