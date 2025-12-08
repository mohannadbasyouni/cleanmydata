# CleanMyData – Development Tasks

## (IN PROGRESS)

- [ ] Fix logs (2 jumps)
- [ ] Add spinning backslash loading bar to verbose mode.
- [ ] Fix user feedback on failing dataset loading. (python main.py data/prodcuts_1M.csv
Loading dataset: prodcuts_1M.csv ⠋
Error: File not found at data/prodcuts_1M.csv
Loading dataset: prodcuts_1M.csv 
Failed to load dataset or file is empty.)
- [ ] Fix user feedback on silent runs (Data cleaned successfully: 0 duplicates, 0 outliers, 0 missing filled (1m 27s).) makes it seem like it did nothing.
- [ ] Change message `(12 columns renamed)` → `12 columns normalized successfully`.
- [ ] Adjust “Text columns cleaned (11 columns)” → `11 text columns cleaned successfully.`
      - Rephrase details as: `Whitespace stripped, spacing standardized, casing normalized.`
- [ ] Review phrasing of “No significant outliers detected.” 
      - Possibly simplify to “No outliers detected.” if detection thresholds confirm no extremes.
- [ ] Add message when no missing values are found (e.g., “No missing values detected.”).
- [ ] Add summary message when no numeric columns required format correction.
- [ ] If numeric columns < X% of total, skip outlier detection and print a message such as:
      - “Outlier analysis skipped (insufficient numeric data).”
- [ ] Add light progress feedback for multi-step cleaning:
      ```
      [1/6] Removing duplicates...
      [2/6] Cleaning text columns...
      ...
      [6/6] Filling missing values...
      ```
- [ ] Add dedicated cleaning for phone numbers, email addresses, and postal addresses.
- [ ] Test across more datasets with different types of dirt.
