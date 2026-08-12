"""Tests for non-interactive distribution validation."""

from app.main import main
from app.smoke import validate_distribution


def test_validate_distribution() -> None:
    """The source tree contains a working model and all runtime assets."""
    validate_distribution()


def test_main_smoke_mode() -> None:
    """The application exposes a successful non-interactive smoke mode."""
    assert main(["--smoke-test"]) == 0
