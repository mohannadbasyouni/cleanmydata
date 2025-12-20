# Project Flow

This document describes how data flows through CleanMyData in both CLI and library modes.

---

## High-level execution flow

```text
User / Automation / Script
│
├── CLI invocation
│   cleanmydata clean input.csv -o output.csv
│
├── OR library usage
│   from cleanmydata import clean_dataframe
│
└── Entry point
    │
    ▼
CLI Layer (Typer)  ── optional
│
│  - parse arguments
│  - determine output mode (normal / quiet / silent)
│  - read config sources
│
▼
Config Boundary
│
│  CLIConfig (Pydantic)
│   - validate CLI args
│   - load env / yaml
│   - coerce types
│
│  ↓ convert
│
│  CleaningConfig (dataclass)
│
▼
AppContext Factory (CLI only)
│
│  - configure named logger
│  - create Rich console (if available)
│  - apply quiet/silent rules
│
▼
I/O Layer
│
│  read_data(path)
│   - validate extension
│   - load CSV / XLSX / XLSM
│
▼
Core Cleaning Pipeline
│
│  clean_dataframe(df, config)
│   - normalize column names
│   - handle missing values
│   - remove duplicates (optional)
│   - detect outliers (optional)
│   - collect warnings / errors
│   - build summary report
│
▼
Output Layer
│
│  write_data(df, output_path)
│
│  - emit summary (unless silent)
│  - log results
│
▼
Return / Exit
│
│  CLI mode:
│   - exit code
│
│  Library mode:
│   - CleaningResult object
