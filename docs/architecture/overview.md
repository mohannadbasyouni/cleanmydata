# Architecture Overview

CleanMyData is designed as a **library-first data cleaning tool** with an optional, polished CLI.
The architecture prioritizes:

- clear separation between **core logic** and **user interface**
- minimal dependencies in library mode
- predictable behavior in automation and scripting
- long-term maintainability and extensibility

The project supports two primary usage modes:

1. **Library mode** — imported and used programmatically
2. **CLI mode** — executed via `cleanmydata` or `python -m cleanmydata`

Both modes share the same core cleaning pipeline.

---

## High-level design principles

### 1. Core vs CLI separation
The cleaning engine lives in the core package and:
- does **not** depend on CLI tools
- does **not** configure logging globally
- returns structured results instead of printing

The CLI layer is responsible for:
- argument parsing
- configuration validation
- console output and progress indicators
- exit codes

This allows CleanMyData to be safely embedded in:
- notebooks
- data pipelines
- larger applications

---

### 2. Explicit configuration boundary
Configuration is handled in two stages:

- **CLIConfig (Pydantic)**
  Used only at the CLI boundary for validation and environment loading.

- **CleaningConfig (dataclass)**
  Passed into the core cleaning functions.
  Contains only primitive types and no external dependencies.

This prevents validation frameworks from leaking into library usage.

---

### 3. Library-safe logging
CleanMyData uses a **named logger** (`cleanmydata`) and never touches the root logger.

- Core code only emits log events
- CLI configures handlers, formatting, verbosity, and output destinations
- Repeated configuration calls are safe (guarded + reset helpers for tests)

This avoids breaking applications that import the library.

---

### 4. Optional features via extras
Heavy or optional functionality is isolated behind **extras**:

- parquet support
- profiling
- schema validation
- documentation tooling

Installing the core library keeps the dependency footprint small.

---

## Target users

- data analysts cleaning CSV/Excel datasets
- developers embedding cleaning logic into pipelines
- automation scripts and CI jobs
- CLI users who want clear, predictable output modes

---

## What this architecture avoids

- global logging configuration
- UI logic mixed into core functions
- hidden side effects
- mandatory heavyweight dependencies
