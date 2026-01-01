# Supported Formats

`cleanmydata` supports reading and writing multiple file formats. The input format is automatically detected from the file extension.

## Format Support Table

| Extension | Format | Required Extra | Notes |
|-----------|--------|----------------|-------|
| `.csv` | Comma Separated Values | None (Core) | Default format. |
| `.xlsx` | Excel Workbook | `excel` | Requires `openpyxl`. |
| `.xlsm` | Excel Macro-Enabled | `excel` | Requires `openpyxl`. |
| `.parquet`| Apache Parquet | `parquet` | Requires `pyarrow`. Efficient for large data. |
| `.xls` | Legacy Excel | **Not Supported** | Explicitly rejected. Please convert to `.xlsx`. |

## Behavior

- **Input:** The tool reads the file based on the extension.
- **Output:** By default, the output file preserves the input extension (e.g., `input.xlsx` -> `input_cleaned.xlsx`). You can change the format by specifying a different extension in `--output` (e.g., convert CSV to Parquet).

## Missing Dependencies

If you try to use a format without the required extra installed, the CLI will error with a helpful hint:

```text
Error: Excel support is not installed.
Hint: Install with: pip install "cleanmydata[excel]"
```
