# Quickstart

Here are common ways to use `cleanmydata`.

## 1. Clean a CSV File

Clean a CSV file with default settings (normalize columns, clean text, handle outliers):

```bash
cleanmydata clean data/messy_leads.csv
```

**Output:**
```text
Cleaned data saved as 'data/messy_leads_cleaned.csv'
```

## 2. Clean an Excel File

Requires `cleanmydata[excel]` installed.

```bash
cleanmydata clean data/sales_report.xlsx --output cleaned_sales.xlsx
```

## 3. Clean a Parquet File

Requires `cleanmydata[parquet]` installed.

```bash
cleanmydata clean data/large_dataset.parquet --auto-outlier-detect
```

## 4. Quiet Mode (Automation Friendly)

Suppress progress bars and info messages, printing only the output path on success (useful for piping).

```bash
# Output path only
cleanmydata clean input.csv --quiet
```

## 5. Silent Mode

No standard output, only exit codes and errors (stderr).

```bash
cleanmydata clean input.csv --silent
# (No output on success)
```
