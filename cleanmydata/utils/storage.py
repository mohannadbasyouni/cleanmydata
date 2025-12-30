"""Lightweight storage helpers (GCS + no-op fallback)."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

from cleanmydata.exceptions import StorageSigningError
from cleanmydata.logging import get_logger

logger = get_logger(__name__)


class StorageClient:
    """Interface for storage clients."""

    backend: str = "base"

    def upload_bytes(self, data: bytes, *, object_name: str, content_type: str) -> str:
        raise NotImplementedError

    def upload_file(self, path: Path, *, object_name: str, content_type: str) -> str:
        raise NotImplementedError

    def download_bytes(self, object_name: str) -> bytes:
        raise NotImplementedError

    def generate_download_url(self, object_name: str, *, expires_seconds: int | None = None) -> str:
        raise NotImplementedError


class NoOpStorageClient(StorageClient):
    """Fallback storage client that does nothing."""

    backend = "noop"

    def upload_bytes(self, data: bytes, *, object_name: str, content_type: str) -> str:  # noqa: ARG002
        logger.debug("storage_upload_skipped", backend=self.backend, object_name=object_name)
        return ""

    def upload_file(self, path: Path, *, object_name: str, content_type: str) -> str:  # noqa: ARG002
        logger.debug("storage_upload_skipped", backend=self.backend, object_name=object_name)
        return ""

    def download_bytes(self, object_name: str) -> bytes:  # noqa: ARG002
        return b""

    def generate_download_url(self, object_name: str, *, expires_seconds: int | None = None) -> str:  # noqa: ARG002
        return ""


class GCSStorageClient(StorageClient):
    """Google Cloud Storage-backed client (lazy imports to keep optional)."""

    backend = "gcs"

    def __init__(
        self,
        bucket_name: str,
        *,
        prefix: str = "cleanmydata/",
        signed_url_ttl: int = 3600,
        client: Any | None = None,
        bucket: Any | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.prefix = self._normalize_prefix(prefix)
        self.signed_url_ttl = signed_url_ttl
        if client is None:
            from google.cloud import storage  # type: ignore

            client = storage.Client()
        self._client = client
        self._bucket = bucket or client.bucket(bucket_name)

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        clean = prefix.strip("/")
        return f"{clean}/" if clean else ""

    def _full_object_name(self, object_name: str) -> str:
        if object_name.startswith(self.prefix):
            return object_name
        return f"{self.prefix}{object_name}"

    @contextmanager
    def _maybe_trace(self, object_name: str, bytes_len: int):
        span = None
        try:
            from ddtrace import tracer as dd_tracer  # type: ignore

            tracer = dd_tracer
        except Exception:
            tracer = None
        if tracer:
            span = tracer.trace("cleanmydata.io.gcs_upload", service="cleanmydata")
            span.set_tag("object_name", object_name)
            span.set_tag("bytes_len", bytes_len)
            span.set_tag("backend", self.backend)
        try:
            yield span
        finally:
            if span:
                span.finish()

    def upload_bytes(self, data: bytes, *, object_name: str, content_type: str) -> str:
        name = self._full_object_name(object_name)
        bytes_len = len(data)
        start = time.perf_counter()
        logger.info(
            "storage_upload_started",
            backend=self.backend,
            object_name=name,
            bytes_len=bytes_len,
        )
        with self._maybe_trace(name, bytes_len) as span:
            try:
                blob = self._bucket.blob(name)
                blob.upload_from_string(data, content_type=content_type)
            except Exception as exc:  # pragma: no cover - exercised in tests via NoOp path
                if span:
                    span.set_tag("error", True)
                    span.set_tag("error.message", str(exc))
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.warning(
                    "storage_upload_failed",
                    backend=self.backend,
                    object_name=name,
                    bytes_len=bytes_len,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                return ""

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "storage_upload_completed",
            backend=self.backend,
            object_name=name,
            bytes_len=bytes_len,
            duration_ms=duration_ms,
        )
        return f"gs://{self.bucket_name}/{name}"

    def upload_file(self, path: Path, *, object_name: str, content_type: str) -> str:
        path = Path(path)
        name = self._full_object_name(object_name)
        bytes_len = path.stat().st_size if path.exists() else 0
        start = time.perf_counter()
        logger.info(
            "storage_upload_started",
            backend=self.backend,
            object_name=name,
            bytes_len=bytes_len,
        )
        with self._maybe_trace(name, bytes_len) as span:
            try:
                blob = self._bucket.blob(name)
                blob.upload_from_filename(str(path), content_type=content_type)
            except Exception as exc:  # pragma: no cover - defensive
                if span:
                    span.set_tag("error", True)
                    span.set_tag("error.message", str(exc))
                duration_ms = int((time.perf_counter() - start) * 1000)
                logger.warning(
                    "storage_upload_failed",
                    backend=self.backend,
                    object_name=name,
                    bytes_len=bytes_len,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                return ""

        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "storage_upload_completed",
            backend=self.backend,
            object_name=name,
            bytes_len=bytes_len,
            duration_ms=duration_ms,
        )
        return f"gs://{self.bucket_name}/{name}"

    def download_bytes(self, object_name: str) -> bytes:
        name = self._full_object_name(object_name)
        blob = self._bucket.blob(name)
        return blob.download_as_bytes()

    def generate_download_url(self, object_name: str, *, expires_seconds: int | None = None) -> str:
        """
        Generate a signed download URL using IAM Credentials API (SignBlob).

        This method uses IAM-only signing and does not require private key material.
        It works on Cloud Run/GCE using the metadata server, or locally with ADC
        (Application Default Credentials via `gcloud auth application-default login`).

        Raises:
            StorageSigningError: If signing fails due to missing permissions or configuration.
        """
        name = self._full_object_name(object_name)
        ttl = expires_seconds if expires_seconds is not None else self.signed_url_ttl

        try:
            import google.auth  # type: ignore
            from google.auth.iam import Signer  # type: ignore
            from google.auth.transport.requests import Request  # type: ignore

            # Get service account email from env var or runtime credentials
            signer_email = os.getenv("CLEANMYDATA_GCS_SIGNER_EMAIL")
            if not signer_email:
                # Try to get it from the default credentials (works on Cloud Run/GCE)
                try:
                    credentials, _ = google.auth.default()
                    # For service account credentials, the service_account_email attribute exists
                    if hasattr(credentials, "service_account_email"):
                        signer_email = credentials.service_account_email
                    elif hasattr(credentials, "signer_email"):
                        signer_email = credentials.signer_email
                except Exception as cred_exc:
                    logger.debug(
                        "storage_signed_url_no_service_account_email",
                        backend=self.backend,
                        error=str(cred_exc),
                    )

            if not signer_email:
                error_msg = (
                    "Cannot generate signed URL: service account email not found. "
                    "Set CLEANMYDATA_GCS_SIGNER_EMAIL environment variable, or ensure "
                    "the runtime is using service account credentials (Cloud Run/GCE)."
                )
                logger.error(
                    "storage_signed_url_missing_service_account_email",
                    backend=self.backend,
                    object_name=name,
                )
                raise StorageSigningError(error_msg)

            # Use IAM Credentials API (SignBlob) - no private key required
            credentials, _ = google.auth.default()
            signer = Signer(Request(), credentials, signer_email)

            logger.info(
                "storage_signed_url_using_iam_signer",
                backend=self.backend,
                service_account_email=signer_email,
                object_name=name,
                ttl=ttl,
            )

            blob = self._bucket.blob(name)
            signed_url = blob.generate_signed_url(
                expiration=timedelta(seconds=ttl),
                method="GET",
                version="v4",
                signer=signer,
                service_account_email=signer_email,
            )

            logger.info(
                "storage_signed_url_success",
                backend=self.backend,
                service_account_email=signer_email,
                object_name=name,
                ttl=ttl,
            )

            return signed_url

        except StorageSigningError:
            raise
        except Exception as exc:
            error_str = str(exc)
            error_lower = error_str.lower()

            # Detect common IAM permission errors
            if "permission" in error_lower or "403" in error_str:
                error_msg = (
                    f"Failed to generate signed URL due to IAM permissions: {error_str}. "
                    "Ensure the service account has the 'roles/iam.serviceAccountTokenCreator' "
                    "role and that the IAM Credentials API (iamcredentials.googleapis.com) is enabled."
                )
            elif "not found" in error_lower or "404" in error_str:
                error_msg = (
                    f"Service account not found or IAM Credentials API not enabled: {error_str}. "
                    "Verify CLEANMYDATA_GCS_SIGNER_EMAIL points to a valid service account and "
                    "that iamcredentials.googleapis.com is enabled in your project."
                )
            else:
                error_msg = (
                    f"Failed to generate signed URL: {error_str}. "
                    "Ensure IAM Credentials API is enabled and the service account has "
                    "the 'roles/iam.serviceAccountTokenCreator' role."
                )

            logger.error(
                "storage_signed_url_failed",
                backend=self.backend,
                service_account_email=signer_email if "signer_email" in locals() else None,
                object_name=name,
                error=error_str,
                exc_info=True,
            )

            raise StorageSigningError(error_msg) from exc


def get_storage_client() -> StorageClient:
    """Return a storage client based on environment configuration."""
    backend = (os.getenv("CLEANMYDATA_STORAGE_BACKEND") or "local").lower()
    bucket = os.getenv("CLEANMYDATA_GCS_BUCKET")
    prefix = os.getenv("CLEANMYDATA_GCS_PREFIX", "cleanmydata/")
    ttl_env = os.getenv("CLEANMYDATA_SIGNED_URL_TTL_SECONDS")

    try:
        ttl = int(ttl_env) if ttl_env else 3600
    except ValueError:
        ttl = 3600

    if backend != "gcs":
        return NoOpStorageClient()

    if not bucket:
        logger.info("storage_backend_not_configured", backend=backend, reason="missing_bucket")
        return NoOpStorageClient()

    # ✅ Explicit dependency check (only about google-cloud-storage)
    try:
        from google.cloud import storage as _storage  # noqa: F401
    except (ImportError, ModuleNotFoundError) as exc:
        logger.debug(
            "storage_backend_unavailable",
            backend=backend,
            reason="missing_google_cloud_storage_dependency",
            error=str(exc),
        )
        return NoOpStorageClient()

    # ✅ Now init; any failure here is NOT "missing dependency"
    try:
        return GCSStorageClient(bucket_name=bucket, prefix=prefix, signed_url_ttl=ttl)
    except Exception as exc:
        logger.warning(
            "storage_backend_init_failed",
            backend=backend,
            error=str(exc),
            exc_info=True,  # <— crucial so you see the real reason in logs
        )
        return NoOpStorageClient()
