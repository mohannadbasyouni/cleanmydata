# CleanMyData

A CLI data cleaning tool for automated cleaning of messy datasets.

---

## Features

- **Duplicate Handling:** Removes duplicate rows with optional subset specification.
- **Column Normalization:** Standardizes column names (lowercase, underscores, removes special characters).
- **Text Cleaning:** Strips whitespace, standardizes spacing, normalizes casing, replaces `"nan"`, `"none"`, `"null"` with missing values.
- **Categorical Normalization:** Optional mapping of categorical values to standardized labels.
- **Format Standardization:**
  - Automatically detects and converts datetime-like and numeric-like columns.
  - Cleans currency, percentage, and formatted number fields.
- **Missing Value Imputation:**
  - Numeric → mean or median (auto-selected based on skewness)
  - Text / Category → mode or `"Unknown"`
  - Datetime → median or auto-inferred pattern
- **Outlier Handling:**
  - `cap` (clip values to IQR bounds)
  - `remove` (drop outlier rows)
- **File Support:** Currently works with `.csv`, `.xls`, and `.xlsx` files.
- **Output:** Saves cleaned data in the `data/` directory with `_cleaned` suffix.
- **Verbose Mode:** Optional detailed logs for every cleaning stage.

---

## Installation

1. Clone the repository:
```bash
   git clone https://github.com/mohannadbasyouni/cleanmydata.git
   cd cleanmydata
```

2. Install dependencies:
```bash
   pip install -r requirements.txt
```

---

## Sample Data

A sample dataset (`retail_sales.csv`) is included in the `data/` folder for testing. For testing with larger datasets (recommended), add your own files to the `data/` directory.

---

## Usage

**Basic:**
```bash
python main.py data/retail_sales.csv
# Output: data/retail_sales_cleaned.csv
```

**Custom Output:**
```bash
python main.py data/retail_sales.csv --output cleaned_sales.csv
```

**Verbose Mode:**
```bash
python main.py data/retail_sales.csv --verbose
```

**Help:**
```bash
python main.py --help
```

---

## License

MIT License. See `LICENSE` for details.
