from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.schema import FIELD_LIMITS, REQUIRED_FIELDS


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""


def validate_numeric_inputs(values: dict[str, str]) -> ValidationResult:
    for k in REQUIRED_FIELDS:
        if k not in values:
            return ValidationResult(False, f"Missing field: {k}")
        if values[k].strip() == "":
            return ValidationResult(False, f"Field '{k}' cannot be empty")

        try:
            value = float(values[k])
        except ValueError:
            return ValidationResult(False, f"Field '{k}' must be a number")

        if not math.isfinite(value):
            return ValidationResult(False, f"Field '{k}' must be finite")

        min_value, max_value = FIELD_LIMITS.get(k, (None, None))
        if min_value is not None and value < min_value:
            return ValidationResult(False, f"Field '{k}' must be >= {min_value:g}")
        if max_value is not None and value > max_value:
            return ValidationResult(False, f"Field '{k}' must be <= {max_value:g}")

    return ValidationResult(True, "OK")


def safe_float(s: str, default: float = 0.0) -> float:
    try:
        value = float(s)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default
