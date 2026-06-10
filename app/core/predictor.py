from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.preprocess import add_engineered_features, preprocess_inputs_dict

try:
    import joblib
except Exception:  # pragma: no cover - fallback when joblib isn't installed
    joblib = None


@dataclass
class Prediction:
    label: int              # 0 safe, 1 dangerous
    prob_dangerous: float   # 0..1
    message: str
    source: str = "model"


class Predictor:
    """
    Predictor with optional real model pipeline; falls back to heuristic when inputs
    don't match the model's expected features.
    """
    MODEL_FILENAME = "decision_tree_pipeline.joblib"
    MODEL_VERSION = "Dummy v0"
    DEFAULT_RATING = 3.0
    _shared_loaded = False
    _shared_pipeline = None
    _shared_features: list[str] = []
    _shared_error: str | None = None

    def __init__(self) -> None:
        self._ensure_loaded()
        self.pipeline = Predictor._shared_pipeline
        self.feature_names = list(Predictor._shared_features)
        self.model_error = Predictor._shared_error

    def predict_one(self, x: dict[str, float]) -> Prediction:
        x_clean = preprocess_inputs_dict(x)
        x_feat = add_engineered_features(x_clean)

        if self.pipeline is not None and self.feature_names:
            df = self._build_model_input(x_feat)
            if df is not None:
                prob = self._predict_proba(df)
                label = 1 if prob >= 0.5 else 0
                msg = "Model prediction completed."
                return Prediction(label=label, prob_dangerous=prob, message=msg, source="model")

            return self._predict_fallback(
                x_feat,
                reason=f"Model expects engineered features ({len(self.feature_names)} fields).",
            )

        return self._predict_fallback(x_feat, reason="Model unavailable.")

    @staticmethod
    def _model_path() -> Path:
        candidates: list[Path] = []
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / Predictor.MODEL_FILENAME)
            candidates.append(Path(sys.executable).resolve().parent / Predictor.MODEL_FILENAME)
        candidates.append(Path(__file__).resolve().parents[2] / Predictor.MODEL_FILENAME)
        candidates.append(Path.cwd() / Predictor.MODEL_FILENAME)

        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    @staticmethod
    def _extract_feature_names(pipeline: Any) -> list[str]:
        if hasattr(pipeline, "feature_names_in_"):
            return list(pipeline.feature_names_in_)
        if hasattr(pipeline, "named_steps"):
            for step in pipeline.named_steps.values():
                if hasattr(step, "feature_names_in_"):
                    return list(step.feature_names_in_)
        return []

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._shared_loaded:
            return
        cls._shared_loaded = True

        model_path = cls._model_path()
        if joblib is None:
            cls._shared_error = "joblib not installed"
            return
        if not model_path.exists():
            cls._shared_error = f"Model file not found: {model_path}"
            return

        try:
            cls._shared_pipeline = joblib.load(model_path)
            cls._shared_features = cls._extract_feature_names(cls._shared_pipeline)
            cls.MODEL_VERSION = "Decision Tree v1 pipeline"
        except Exception as exc:  # pragma: no cover - defensive
            cls._shared_pipeline = None
            cls._shared_error = str(exc)

    @classmethod
    def model_version(cls) -> str:
        cls._ensure_loaded()
        return cls.MODEL_VERSION

    @classmethod
    def model_status(cls) -> str:
        cls._ensure_loaded()
        if cls._shared_error:
            return f"{cls.MODEL_VERSION} (error: {cls._shared_error})"
        return cls.MODEL_VERSION

    def _predict_proba(self, df: pd.DataFrame) -> float:
        if hasattr(self.pipeline, "predict_proba"):
            proba = self.pipeline.predict_proba(df)[0]
            classes = None
            if hasattr(self.pipeline, "classes_"):
                classes = list(self.pipeline.classes_)
            elif hasattr(self.pipeline, "named_steps"):
                model = self.pipeline.named_steps.get("model")
                if model is not None and hasattr(model, "classes_"):
                    classes = list(model.classes_)
            if classes and 1 in classes:
                return float(proba[classes.index(1)])
            return float(proba[-1])
        pred = self.pipeline.predict(df)[0]
        return float(pred)

    def _build_model_input(self, x_feat: dict[str, float]) -> pd.DataFrame | None:
        row: dict[str, float] = {}
        missing: list[str] = []

        for name in self.feature_names:
            if name in x_feat:
                row[name] = float(x_feat.get(name, 0.0))
                continue

            if name.startswith("num__"):
                base = name[len("num__"):]
                if base in x_feat:
                    row[name] = float(x_feat.get(base, 0.0))
                    continue

            if name in ("rating", "num__rating"):
                row[name] = float(self.DEFAULT_RATING)
                continue

            missing.append(name)

        if missing:
            return None
        return pd.DataFrame([row])

    def _predict_fallback(self, x: dict[str, float], reason: str) -> Prediction:
        """
        Heuristic fallback:
        - Higher speed + strong acceleration + strong gyro => more dangerous
        """
        speed = x.get("speed", 0.0)
        ax = abs(x.get("acceleration_x", 0.0))
        ay = abs(x.get("acceleration_y", 0.0))
        az = abs(x.get("acceleration_z", 0.0))
        gx = abs(x.get("gyro_x", 0.0))
        gy = abs(x.get("gyro_y", 0.0))
        gz = abs(x.get("gyro_z", 0.0))

        score = (
            0.12 * speed
            + 0.25 * (ax + ay + az)
            + 0.18 * (gx + gy + gz)
        )

        prob = 1.0 / (1.0 + math.exp(-(score - 6.5)))
        prob = float(np.clip(prob, 0.0, 1.0))

        label = 1 if prob >= 0.5 else 0
        msg = "High-risk driving pattern detected." if label == 1 else "Looks normal based on sensor pattern."
        msg = f"{msg} (Heuristic fallback used: {reason})"

        return Prediction(label=label, prob_dangerous=prob, message=msg, source="heuristic_fallback")
