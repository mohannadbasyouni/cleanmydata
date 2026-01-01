import subprocess
import sys


def test_public_api_exports_required_symbols():
    import cleanmydata

    required = [
        "clean_file",
        "read_data",
        "write_data",
        "InvalidInputError",
        "CleanIOError",
    ]
    for name in required:
        assert hasattr(cleanmydata, name)
        assert name in cleanmydata.__all__

    from cleanmydata import (  # noqa: F401
        CleanIOError,
        InvalidInputError,
        clean_file,
        read_data,
        write_data,
    )


def test_import_cleanmydata_is_lightweight():
    # Verify importing cleanmydata doesn't eagerly import heavy deps like pandas.
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import cleanmydata; print('pandas' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout.strip() == "False"
