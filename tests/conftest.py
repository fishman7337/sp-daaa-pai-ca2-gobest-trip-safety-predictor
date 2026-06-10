import pytest

from app.core.validation import REQUIRED_FIELDS


@pytest.fixture
def valid_inputs() -> dict[str, str]:
    return {field: "1.5" for field in REQUIRED_FIELDS}
