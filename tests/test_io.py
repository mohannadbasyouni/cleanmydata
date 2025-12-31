"""Tests for I/O utilities."""

from pathlib import Path

import pytest

from cleanmydata.utils.io import read_data


def test_read_data_file_not_found():
    """Test that read_data raises FileNotFoundError for non-existent files."""
    path = Path("nonexistent_file.csv")
    with pytest.raises(FileNotFoundError):
        read_data(path)
