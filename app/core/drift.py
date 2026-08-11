"""Detect distribution drift in trip sensor features."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DriftReport:
    """Describe the outcome of a feature drift analysis.

    Attributes:
        drifted: Whether any monitored feature crossed the drift threshold.
        score: Largest absolute standardized mean difference.
        feature_scores: Standardized mean differences keyed by feature.
        message: Human-readable analysis status.
        ref_ready: Whether the reference baseline is available.
        window_ready: Whether the recent comparison window is available.
    """

    drifted: bool
    score: float
    feature_scores: dict[str, float]
    message: str
    ref_ready: bool
    window_ready: bool


class DriftMonitor:
    """Compare recent feature means with a learned reference baseline."""

    def __init__(
        self,
        fields: list[str],
        reference_size: int = 40,
        window_size: int = 20,
        z_threshold: float = 3.0,
    ) -> None:
        """Configure the reference and rolling comparison windows.

        Args:
            fields: Feature names to monitor.
            reference_size: Samples used to establish the baseline.
            window_size: Recent samples used for each comparison.
            z_threshold: Absolute standardized difference that signals drift.

        Raises:
            ValueError: If either sample window is smaller than five.
        """
        if reference_size < 5:
            raise ValueError("reference_size must be >= 5")
        if window_size < 5:
            raise ValueError("window_size must be >= 5")
        self.fields = list(fields)
        self.reference_size = reference_size
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._reference_samples: list[list[float]] = []
        self._window = deque(maxlen=window_size)
        self._ref_mean: np.ndarray | None = None
        self._ref_std: np.ndarray | None = None

    def reset_reference(self) -> None:
        """Discard the learned baseline and all recent samples."""
        self._reference_samples = []
        self._window.clear()
        self._ref_mean = None
        self._ref_std = None

    def update(self, sample: dict[str, float]) -> DriftReport:
        """Ingest one sample and report current drift status.

        Args:
            sample: Numeric feature values keyed by monitored field name.

        Returns:
            The baseline collection, window collection, or drift status.
        """
        vector = [float(sample.get(f, 0.0)) for f in self.fields]

        if self._ref_mean is None or self._ref_std is None:
            self._reference_samples.append(vector)
            if len(self._reference_samples) < self.reference_size:
                return DriftReport(
                    drifted=False,
                    score=0.0,
                    feature_scores={},
                    message=f"Collecting baseline: {len(self._reference_samples)}/{self.reference_size}",
                    ref_ready=False,
                    window_ready=False,
                )
            self._set_reference(np.array(self._reference_samples))
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message="Baseline ready. Collecting recent window.",
                ref_ready=True,
                window_ready=False,
            )

        self._window.append(vector)
        if len(self._window) < self.window_size:
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message=f"Collecting recent window: {len(self._window)}/{self.window_size}",
                ref_ready=True,
                window_ready=False,
            )

        return self._compute_report(np.array(self._window))

    def analyze_dataframe(self, df: pd.DataFrame) -> DriftReport:
        """Compare the leading and trailing windows of a data frame.

        Args:
            df: Frame containing every configured feature field.

        Returns:
            A drift report or a readiness explanation for unsuitable input.
        """
        if df.empty:
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message="No data to analyze.",
                ref_ready=False,
                window_ready=False,
            )

        available = [f for f in self.fields if f in df.columns]
        if len(available) != len(self.fields):
            missing = [f for f in self.fields if f not in df.columns]
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message=f"Missing fields for drift analysis: {missing}",
                ref_ready=False,
                window_ready=False,
            )

        if len(df) < self.reference_size + self.window_size:
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message="Not enough rows for drift analysis.",
                ref_ready=False,
                window_ready=False,
            )

        ref = df.iloc[: self.reference_size][self.fields].to_numpy(dtype=float)
        window = df.iloc[-self.window_size :][self.fields].to_numpy(dtype=float)
        self._set_reference(ref)
        return self._compute_report(window)

    def _set_reference(self, data: np.ndarray) -> None:
        self._ref_mean = np.mean(data, axis=0)
        self._ref_std = np.std(data, axis=0)

    def _compute_report(self, window: np.ndarray) -> DriftReport:
        if self._ref_mean is None or self._ref_std is None:
            return DriftReport(
                drifted=False,
                score=0.0,
                feature_scores={},
                message="Baseline not ready.",
                ref_ready=False,
                window_ready=False,
            )

        win_mean = np.mean(window, axis=0)
        eps = 1e-6
        z = np.abs(win_mean - self._ref_mean) / (self._ref_std + eps)
        feature_scores = {f: float(z[i]) for i, f in enumerate(self.fields)}
        max_z = float(np.max(z))

        drifted_features = [f for f, score in feature_scores.items() if score >= self.z_threshold]
        drifted = len(drifted_features) > 0

        if drifted:
            top = ", ".join(drifted_features[:3])
            msg = f"Drift detected in: {top} (max z={max_z:.2f})"
        else:
            msg = f"No significant drift (max z={max_z:.2f})"

        return DriftReport(
            drifted=drifted,
            score=max_z,
            feature_scores=feature_scores,
            message=msg,
            ref_ready=True,
            window_ready=True,
        )
