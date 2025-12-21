"""Constants used throughout the cleanmydata package."""

# Supported file formats for reading/writing
# IMPORTANT: Do NOT include .parquet yet (will be added in Phase 4)
CORE_FORMATS = {".csv"}
# Excel formats require the optional extra: `pip install "cleanmydata[excel]"`.
EXCEL_FORMATS = {".xlsx", ".xlsm"}
SUPPORTED_FORMATS = CORE_FORMATS | EXCEL_FORMATS

# Outlier handling methods
OUTLIER_METHODS = ["cap", "remove", None]

# Default cleaning configuration values
DEFAULT_OUTLIER_METHOD = "cap"
DEFAULT_NORMALIZE_COLS = True
DEFAULT_CLEAN_TEXT = True
DEFAULT_AUTO_OUTLIER_DETECT = True
