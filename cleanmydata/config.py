"""Configuration settings for the cleanmydata package."""

from dataclasses import dataclass


@dataclass
class CleaningConfig:
    """
    Configuration for data cleaning operations.

    This is a core dataclass used by the cleaning pipeline.
    CLI layer should use CLIConfig (Pydantic) and convert to this.
    """

    outliers: str = "cap"
    normalize_cols: bool = True
    clean_text: bool = True
    categorical_mapping: dict[str, dict[str, str]] | None = None
    auto_outlier_detect: bool = True
    verbose: bool = False
    profile: bool = False

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid
        """
        from cleanmydata.constants import OUTLIER_METHODS
        from cleanmydata.exceptions import ValidationError

        if self.outliers not in OUTLIER_METHODS:
            raise ValidationError(
                f"Invalid outlier method: {self.outliers}. Must be one of: {OUTLIER_METHODS}"
            )

        if self.categorical_mapping is not None:
            if not isinstance(self.categorical_mapping, dict):
                raise ValidationError("categorical_mapping must be a dictionary")
            for col, mapping in self.categorical_mapping.items():
                if not isinstance(mapping, dict):
                    raise ValidationError(
                        f"categorical_mapping[{col}] must be a dictionary mapping old to new values"
                    )
