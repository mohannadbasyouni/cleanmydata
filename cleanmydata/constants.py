"""Constants used throughout the cleanmydata package."""

# Supported file formats for reading/writing
# IMPORTANT: Do NOT include .parquet yet (will be added in Phase 4)
SUPPORTED_FORMATS = {".csv", ".xlsx", ".xlsm"}

# Outlier handling methods
OUTLIER_METHODS = ["cap", "remove", None]

# Default cleaning configuration values
DEFAULT_OUTLIER_METHOD = "cap"
DEFAULT_NORMALIZE_COLS = True
DEFAULT_CLEAN_TEXT = True
DEFAULT_AUTO_OUTLIER_DETECT = True
