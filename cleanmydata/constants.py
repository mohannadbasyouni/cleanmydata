"""Constants used throughout the cleanmydata package."""

# Exit codes (CLI contract)
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_INPUT = 2
EXIT_IO_ERROR = 3

# Supported file formats for reading/writing
CORE_FORMATS = {".csv"}
# Excel formats require the optional extra: `pip install "cleanmydata[excel]"`.
EXCEL_FORMATS = {".xlsx", ".xlsm"}
PARQUET_FORMATS = {".parquet"}
SUPPORTED_FORMATS = CORE_FORMATS | EXCEL_FORMATS | PARQUET_FORMATS

# Outlier handling methods
OUTLIER_METHODS = ["cap", "remove", None]

# Default cleaning configuration values
DEFAULT_OUTLIER_METHOD = "cap"
DEFAULT_NORMALIZE_COLS = True
DEFAULT_CLEAN_TEXT = True
DEFAULT_AUTO_OUTLIER_DETECT = True
