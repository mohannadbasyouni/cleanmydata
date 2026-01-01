# Installation

`cleanmydata` requires Python 3.10 or higher.

## Base Installation

For basic CSV cleaning support:

```bash
pip install cleanmydata
```

## Optional Dependencies (Extras)

To keep the installation lightweight, support for other formats and features is available via extras.

| Feature | Extra | Install Command |
|---------|-------|-----------------|
| Excel Support (`.xlsx`, `.xlsm`) | `excel` | `pip install "cleanmydata[excel]"` |
| Parquet Support (`.parquet`) | `parquet` | `pip install "cleanmydata[parquet]"` |
| API Server | `api` | `pip install "cleanmydata[api]"` |
| Schema Validation | `schema` | `pip install "cleanmydata[schema]"` |
| CLI Enhancements (Rich/Typer) | `cli` | `pip install "cleanmydata[cli]"` |
| **All Features** | `all` | `pip install "cleanmydata[all]"` |

## Verification

Verify the installation by checking the version:

```bash
cleanmydata --help
```
