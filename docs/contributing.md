# Contributing

We welcome contributions to `cleanmydata`.

## Development Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/cleanmydata.git
    cd cleanmydata
    ```

2.  **Install dependencies:**
    We use `pip` with extras for development.
    ```bash
    pip install -e ".[dev,test,all]"
    ```

## Running Checks

Before submitting a PR, ensure your code passes our quality checks.

-   **Format:**
    ```bash
    ruff format .
    ```

-   **Lint:**
    ```bash
    ruff check .
    ```

-   **Test:**
    ```bash
    # Run all tests
    pytest

    # Run core tests (skip extras if not installed)
    pytest -k "not excel and not parquet"
    ```

-   **Type Check:**
    ```bash
    mypy .
    ```

## Pull Request Guidelines

1.  Create a branch: `feature/your-feature-name` or `fix/issue-description`.
2.  Keep changes focused and minimal.
3.  Add tests for new functionality.
4.  Update documentation if behavior changes.
5.  Wait for CI to pass before merging.
