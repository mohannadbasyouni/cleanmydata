# Configuration

`cleanmydata` configuration is resolved in the following precedence order (highest priority last):

1.  **Recipe** (Defaults defined in a recipe file)
2.  **Config File** (YAML file)
3.  **Environment Variables**
4.  **CLI Arguments** (Explicit flags override everything)

## Configuration Options

| Option | Type | CLI Flag | Env Variable | Default |
|--------|------|----------|--------------|---------|
| Path | Path | `path` (arg) | `CLEANMYDATA_PATH` | (Required) |
| Output | Path | `--output` | `CLEANMYDATA_OUTPUT` | `original_cleaned.ext` |
| Outlier Strategy | `cap`, `remove`, `none` | `--outliers` | `CLEANMYDATA_OUTLIERS` | `cap` |
| Normalize Columns | Boolean | `--normalize-cols` | `CLEANMYDATA_NORMALIZE_COLS` | `true` |
| Clean Text | Boolean | `--clean-text` | `CLEANMYDATA_CLEAN_TEXT` | `true` |
| Auto Outlier Detect | Boolean | `--auto-outlier-detect` | `CLEANMYDATA_AUTO_OUTLIER_DETECT` | `true` |
| Verbose | Boolean | `--verbose` | `CLEANMYDATA_VERBOSE` | `false` |
| Quiet | Boolean | `--quiet` | `CLEANMYDATA_QUIET` | `false` |
| Silent | Boolean | `--silent` | `CLEANMYDATA_SILENT` | `false` |

## YAML Config Example

Create a `cleanmydata.yaml` file:

```yaml
outliers: remove
normalize_cols: true
clean_text: false
verbose: true
```

Usage:
```bash
cleanmydata clean input.csv --config cleanmydata.yaml
```

## Environment Variables Example

```bash
export CLEANMYDATA_OUTLIERS=remove
export CLEANMYDATA_VERBOSE=true
cleanmydata clean input.csv
```
