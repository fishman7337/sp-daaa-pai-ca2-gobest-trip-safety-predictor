from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock

LOGGER = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    booking_id: str
    felt_safe: bool
    rating: int
    notes: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PredictionEntry:
    booking_id: str
    predicted_label: int
    prob_dangerous: float
    created_at: datetime = field(default_factory=datetime.utcnow)


class DataStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._feedback: list[FeedbackEntry] = []
        self._predictions: dict[str, PredictionEntry] = {}
        self._listeners: list[Callable[[], None]] = []
        self.last_booking_id: str = ""

    def new_booking_id(self) -> str:
        return f"BK-{uuid.uuid4().hex[:8].upper()}"

    def add_prediction(self, entry: PredictionEntry) -> None:
        with self._lock:
            if entry.booking_id in self._predictions:
                raise ValueError("Booking ID already exists.")
            self._predictions[entry.booking_id] = entry
            self.last_booking_id = entry.booking_id
        self._notify()

    def add_feedback(self, entry: FeedbackEntry) -> None:
        with self._lock:
            if entry.booking_id not in self._predictions:
                raise ValueError("Booking ID not found. Predict first.")
            if any(f.booking_id == entry.booking_id for f in self._feedback):
                raise ValueError("Feedback already submitted for this Booking ID.")
            self._feedback.append(entry)
        self._notify()

    def all_feedback(self) -> list[FeedbackEntry]:
        with self._lock:
            return list(self._feedback)

    def all_predictions(self) -> list[PredictionEntry]:
        with self._lock:
            return list(self._predictions.values())

    def get_prediction(self, booking_id: str) -> PredictionEntry | None:
        with self._lock:
            return self._predictions.get(booking_id)

    def recent_booking_ids(self, limit: int = 10) -> list[str]:
        with self._lock:
            return [p.booking_id for p in list(self._predictions.values())[-limit:]]

    def export_rows(self) -> list[dict[str, str]]:
        with self._lock:
            feedback_rows = list(self._feedback)
            predictions = dict(self._predictions)

        rows: list[dict[str, str]] = []
        for feedback in feedback_rows:
            pred = predictions.get(feedback.booking_id)
            if pred is None:
                continue
            actual_label = 0 if feedback.felt_safe else 1
            match_flag = "yes" if actual_label == pred.predicted_label else "no"
            rows.append(
                {
                    "booking_id": feedback.booking_id,
                    "predicted_label": str(pred.predicted_label),
                    "actual_label": str(actual_label),
                    "rating": str(feedback.rating),
                    "match": match_flag,
                }
            )
        return rows

    def stats(self) -> dict[str, float]:
        with self._lock:
            feedback_rows = list(self._feedback)
            predictions = dict(self._predictions)

        total_feedback = len(feedback_rows)
        total_predictions = len(predictions)
        if total_feedback == 0:
            return {
                "total": 0,
                "total_predictions": total_predictions,
                "feedback_rate": 0.0,
                "safe_ratio": 0.0,
                "avg_rating": 0.0,
                "match_rate": 0.0,
            }
        safe_count = sum(1 for f in feedback_rows if f.felt_safe)
        avg_rating = sum(f.rating for f in feedback_rows) / total_feedback
        matched = 0
        for f in feedback_rows:
            pred = predictions.get(f.booking_id)
            if pred is None:
                continue
            actual_label = 0 if f.felt_safe else 1
            if actual_label == pred.predicted_label:
                matched += 1
        match_rate = matched / total_feedback if total_feedback else 0.0
        feedback_rate = total_feedback / total_predictions if total_predictions else 0.0
        return {
            "total": total_feedback,
            "total_predictions": total_predictions,
            "feedback_rate": feedback_rate,
            "safe_ratio": safe_count / total_feedback,
            "avg_rating": avg_rating,
            "match_rate": match_rate,
        }

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)

        return unsubscribe

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback()
            except Exception:
                LOGGER.exception("DataStore listener failed")
