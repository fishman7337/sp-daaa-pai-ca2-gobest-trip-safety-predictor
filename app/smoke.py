"""Non-interactive validation for source and packaged distributions."""

from __future__ import annotations

from pathlib import Path

from app.core.predictor import Predictor

EXPECTED_ASSETS = (
    "about.png",
    "admin.png",
    "batch.png",
    "feedback.png",
    "realtime.png",
)


def validate_distribution() -> None:
    """Validate model inference and UI resources required at runtime.

    Raises:
        RuntimeError: If the model cannot run or a required asset is missing.

    """
    predictor = Predictor()
    if predictor.pipeline is None or not predictor.feature_names:
        raise RuntimeError(f"model unavailable: {Predictor.model_status()}")

    sample = {field.removeprefix("num__"): 1.5 for field in predictor.feature_names}
    prediction = predictor.predict_one(sample)
    if prediction.source != "model":
        raise RuntimeError(f"model inference used unexpected source: {prediction.source}")

    assets_dir = Path(__file__).resolve().parent / "ui" / "assets"
    missing_assets = [name for name in EXPECTED_ASSETS if not (assets_dir / name).is_file()]
    if missing_assets:
        missing = ", ".join(missing_assets)
        raise RuntimeError(f"missing UI assets: {missing}")
