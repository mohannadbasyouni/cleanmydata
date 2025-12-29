from __future__ import annotations

import builtins
import sys
import types
from datetime import timedelta
from pathlib import Path

import pytest

from cleanmydata.logging import configure_logging_json, reset_logging_for_tests
from cleanmydata.utils.storage import (
    GCSStorageClient,
    NoOpStorageClient,
    get_storage_client,
)


def _install_fake_gcs(monkeypatch: pytest.MonkeyPatch):
    """Install a fake google.cloud.storage module for testing."""

    class FakeBlob:
        def __init__(self, name: str) -> None:
            self.name = name
            self.uploads: list[tuple[bytes, str | None]] = []
            self.last_expiration: timedelta | None = None
            self.uploaded_from_filename: str | None = None

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
            **kwargs,  # noqa: ARG002
        ) -> str:
            self.last_expiration = expiration
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

    storage_mod = types.ModuleType("google.cloud.storage")
    storage_mod.Client = FakeClient

    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    cloud_mod.storage = storage_mod
    google_mod.cloud = cloud_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_mod)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage_mod)

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
    fake_bucket = _install_fake_gcs(monkeypatch)
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


def test_generate_download_url_respects_env_ttl(monkeypatch):
    fake_bucket = _install_fake_gcs(monkeypatch)
    monkeypatch.setenv("CLEANMYDATA_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("CLEANMYDATA_GCS_BUCKET", "env-bucket")
    monkeypatch.setenv("CLEANMYDATA_SIGNED_URL_TTL_SECONDS", "120")

    client = get_storage_client()
    assert isinstance(client, GCSStorageClient)

    _ = client.generate_download_url("job-999/cleaned.csv")

    assert fake_bucket.last_blob is not None
    assert fake_bucket.last_blob.last_expiration == timedelta(seconds=120)
