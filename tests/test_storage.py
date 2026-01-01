from __future__ import annotations

import builtins
import sys
import types
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from cleanmydata.exceptions import StorageSigningError
from cleanmydata.utils.logging import configure_logging_json, reset_logging_for_tests
from cleanmydata.utils.storage import (
    GCSStorageClient,
    NoOpStorageClient,
    get_storage_client,
)


def _install_fake_gcs(monkeypatch: pytest.MonkeyPatch, signer_email: str | None = None):
    """Install a fake google.cloud.storage and google.auth modules for testing."""

    class FakeBlob:
        def __init__(self, name: str) -> None:
            self.name = name
            self.uploads: list[tuple[bytes, str | None]] = []
            self.last_expiration: timedelta | None = None
            self.uploaded_from_filename: str | None = None
            self.last_signer: Any | None = None
            self.last_service_account_email: str | None = None

        def upload_from_string(self, data: bytes, content_type: str | None = None) -> None:
            self.uploads.append((data, content_type))

        def upload_from_filename(self, filename: str, content_type: str | None = None) -> None:
            self.uploaded_from_filename = filename
            self.uploads.append((Path(filename).read_bytes(), content_type))

        def download_as_bytes(self) -> bytes:
            return b""

        def generate_signed_url(
            self,
            expiration: timedelta,
            method: str = "GET",  # noqa: ARG002
            version: str | None = None,  # noqa: ARG002
            signer: Any | None = None,
            service_account_email: str | None = None,
            **kwargs,  # noqa: ARG002
        ) -> str:
            self.last_expiration = expiration
            self.last_signer = signer
            self.last_service_account_email = service_account_email
            # Verify that signer is provided (IAM signing path)
            if signer is None:
                raise ValueError("signer is required for IAM-only signing")
            return f"https://signed/{self.name}"

    class FakeBucket:
        def __init__(self, name: str) -> None:
            self.name = name
            self.last_blob: FakeBlob | None = None

        def blob(self, name: str) -> FakeBlob:
            blob = FakeBlob(name)
            self.last_blob = blob
            return blob

    fake_bucket = FakeBucket("bucket")

    class FakeClient:
        def bucket(self, name: str) -> FakeBucket:
            fake_bucket.name = name
            return fake_bucket

    # Fake google.cloud.storage
    storage_mod = types.ModuleType("google.cloud.storage")
    storage_mod.Client = FakeClient

    # Fake google.auth
    class FakeCredentials:
        def __init__(self, email: str | None = None) -> None:
            self.service_account_email = email
            self.signer_email = email

    class FakeRequest:
        pass

    class FakeSigner:
        def __init__(self, request: Any, credentials: Any, email: str) -> None:  # noqa: ARG002
            self.email = email

    def fake_default():
        return (FakeCredentials(email=signer_email), None)

    auth_mod = types.ModuleType("google.auth")
    auth_mod.default = fake_default
    auth_mod.iam = types.ModuleType("google.auth.iam")
    auth_mod.iam.Signer = FakeSigner
    auth_mod.transport = types.ModuleType("google.auth.transport")
    auth_mod.transport.requests = types.ModuleType("google.auth.transport.requests")
    auth_mod.transport.requests.Request = FakeRequest

    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    cloud_mod.storage = storage_mod
    google_mod.cloud = cloud_mod
    google_mod.auth = auth_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_mod)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage_mod)
    monkeypatch.setitem(sys.modules, "google.auth", auth_mod)
    monkeypatch.setitem(sys.modules, "google.auth.iam", auth_mod.iam)
    monkeypatch.setitem(sys.modules, "google.auth.transport", auth_mod.transport)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", auth_mod.transport.requests)

    return fake_bucket


def test_get_storage_client_defaults_to_noop(monkeypatch):
    monkeypatch.delenv("CLEANMYDATA_STORAGE_BACKEND", raising=False)
    client = get_storage_client()
    assert isinstance(client, NoOpStorageClient)
    assert client.upload_bytes(b"hi", object_name="x", content_type="text/plain") == ""
    assert client.generate_download_url("x") == ""


def test_get_storage_client_gcs_missing_dependency(monkeypatch, capsys):
    monkeypatch.setenv("CLEANMYDATA_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("CLEANMYDATA_GCS_BUCKET", "my-bucket")
    reset_logging_for_tests()
    configure_logging_json(level="DEBUG")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ANN001
        if name.startswith("google.cloud"):
            raise ImportError("no gcs")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    client = get_storage_client()
    out, _ = capsys.readouterr()

    assert isinstance(client, NoOpStorageClient)
    assert "storage_backend_unavailable" in out


def test_gcs_upload_and_signed_url(monkeypatch, tmp_path):
    fake_bucket = _install_fake_gcs(monkeypatch, signer_email="test@example.com")
    monkeypatch.setenv("CLEANMYDATA_GCS_SIGNER_EMAIL", "test@example.com")
    data_path = Path(tmp_path) / "out.csv"
    data_path.write_text("a,b\n1,2\n")

    client = GCSStorageClient("my-bucket", prefix="cleanmydata/", signed_url_ttl=900)
    result = client.upload_file(
        data_path, object_name="job-123/cleaned.csv", content_type="text/csv"
    )

    assert result == "gs://my-bucket/cleanmydata/job-123/cleaned.csv"
    assert fake_bucket.last_blob is not None
    assert fake_bucket.last_blob.uploads[-1][0] == data_path.read_bytes()
    assert fake_bucket.last_blob.uploaded_from_filename == str(data_path)

    signed_url = client.generate_download_url("job-123/cleaned.csv")
    assert signed_url == "https://signed/cleanmydata/job-123/cleaned.csv"
    assert fake_bucket.last_blob.last_expiration == timedelta(seconds=900)
    # Verify IAM signing was used (signer provided, no private key)
    assert fake_bucket.last_blob.last_signer is not None
    assert fake_bucket.last_blob.last_service_account_email == "test@example.com"


def test_generate_download_url_respects_env_ttl(monkeypatch):
    fake_bucket = _install_fake_gcs(monkeypatch, signer_email="test@example.com")
    monkeypatch.setenv("CLEANMYDATA_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("CLEANMYDATA_GCS_BUCKET", "env-bucket")
    monkeypatch.setenv("CLEANMYDATA_GCS_SIGNER_EMAIL", "test@example.com")
    monkeypatch.setenv("CLEANMYDATA_SIGNED_URL_TTL_SECONDS", "120")

    client = get_storage_client()
    assert isinstance(client, GCSStorageClient)

    _ = client.generate_download_url("job-999/cleaned.csv")

    assert fake_bucket.last_blob is not None
    assert fake_bucket.last_blob.last_expiration == timedelta(seconds=120)
    # Verify IAM signing was used
    assert fake_bucket.last_blob.last_signer is not None


def test_generate_download_url_uses_iam_signer_no_private_key(monkeypatch):
    """Test that signed URL generation uses IAM signing and does not require private key."""
    fake_bucket = _install_fake_gcs(
        monkeypatch, signer_email="test-sa@project.iam.gserviceaccount.com"
    )
    monkeypatch.setenv("CLEANMYDATA_GCS_SIGNER_EMAIL", "test-sa@project.iam.gserviceaccount.com")

    client = GCSStorageClient("my-bucket")
    signed_url = client.generate_download_url("test/file.csv")

    assert signed_url.startswith("https://signed/")
    # Verify signer was provided (IAM path) - this means no private key was used
    assert fake_bucket.last_blob is not None
    assert fake_bucket.last_blob.last_signer is not None
    assert (
        fake_bucket.last_blob.last_service_account_email
        == "test-sa@project.iam.gserviceaccount.com"
    )


def test_generate_download_url_gets_email_from_credentials(monkeypatch):
    """Test that service account email is obtained from credentials if not in env."""
    fake_bucket = _install_fake_gcs(
        monkeypatch, signer_email="runtime-sa@project.iam.gserviceaccount.com"
    )
    monkeypatch.delenv("CLEANMYDATA_GCS_SIGNER_EMAIL", raising=False)

    client = GCSStorageClient("my-bucket")
    signed_url = client.generate_download_url("test/file.csv")

    assert signed_url.startswith("https://signed/")
    assert fake_bucket.last_blob is not None
    assert (
        fake_bucket.last_blob.last_service_account_email
        == "runtime-sa@project.iam.gserviceaccount.com"
    )


def test_generate_download_url_raises_error_when_no_service_account_email(monkeypatch):
    """Test that StorageSigningError is raised when service account email cannot be determined."""
    _install_fake_gcs(monkeypatch, signer_email=None)
    monkeypatch.delenv("CLEANMYDATA_GCS_SIGNER_EMAIL", raising=False)

    client = GCSStorageClient("my-bucket")

    with pytest.raises(StorageSigningError) as exc_info:
        client.generate_download_url("test/file.csv")

    assert "service account email" in str(exc_info.value).lower()
    assert "CLEANMYDATA_GCS_SIGNER_EMAIL" in str(exc_info.value)


def test_generate_download_url_raises_error_on_permission_failure(monkeypatch):
    """Test that StorageSigningError provides helpful message on IAM permission errors."""

    # Create a fake bucket with a blob that raises permission errors
    class FailingFakeBlob:
        def __init__(self, name: str) -> None:
            self.name = name

        def generate_signed_url(self, *args, **kwargs):  # noqa: ARG002
            raise Exception("403 Permission denied")

    class FailingFakeBucket:
        def blob(self, name: str) -> FailingFakeBlob:
            return FailingFakeBlob(name)

    fake_bucket = FailingFakeBucket()

    # Install fake modules
    class FakeClient:
        def bucket(self, name: str) -> FailingFakeBucket:  # noqa: ARG002
            return fake_bucket

    storage_mod = types.ModuleType("google.cloud.storage")
    storage_mod.Client = FakeClient

    class FakeCredentials:
        def __init__(self) -> None:
            self.service_account_email = "test@example.com"

    class FakeRequest:
        pass

    class FakeSigner:
        def __init__(self, request: Any, credentials: Any, email: str) -> None:  # noqa: ARG002
            self.email = email

    auth_mod = types.ModuleType("google.auth")
    auth_mod.default = lambda: (FakeCredentials(), None)
    auth_mod.iam = types.ModuleType("google.auth.iam")
    auth_mod.iam.Signer = FakeSigner
    auth_mod.transport = types.ModuleType("google.auth.transport")
    auth_mod.transport.requests = types.ModuleType("google.auth.transport.requests")
    auth_mod.transport.requests.Request = FakeRequest

    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    cloud_mod.storage = storage_mod
    google_mod.cloud = cloud_mod
    google_mod.auth = auth_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_mod)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage_mod)
    monkeypatch.setitem(sys.modules, "google.auth", auth_mod)
    monkeypatch.setitem(sys.modules, "google.auth.iam", auth_mod.iam)
    monkeypatch.setitem(sys.modules, "google.auth.transport", auth_mod.transport)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", auth_mod.transport.requests)

    monkeypatch.setenv("CLEANMYDATA_GCS_SIGNER_EMAIL", "test@example.com")

    client = GCSStorageClient("my-bucket")

    with pytest.raises(StorageSigningError) as exc_info:
        client.generate_download_url("test/file.csv")

    error_msg = str(exc_info.value)
    assert "permission" in error_msg.lower() or "403" in error_msg
    assert "iam.serviceAccountTokenCreator" in error_msg
    assert "iamcredentials.googleapis.com" in error_msg
