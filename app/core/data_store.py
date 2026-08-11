"""Store predictions and rider feedback safely in memory."""

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
    """Represent rider feedback associated with a booking.

    Attributes:
        booking_id: Booking identifier tied to an existing prediction.
        felt_safe: Whether the rider reported feeling safe.
        rating: Numeric rating supplied by the rider.
        notes: Free-form rider comments.
        created_at: Time at which the feedback entry was created.
    """

    booking_id: str
    felt_safe: bool
    rating: int
    notes: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PredictionEntry:
    """Represent a stored trip safety prediction.

    Attributes:
        booking_id: Unique booking identifier.
        predicted_label: Predicted class, where zero is safe and one is dangerous.
        prob_dangerous: Estimated probability of the dangerous class.
        created_at: Time at which the prediction entry was created.
    """

    booking_id: str
    predicted_label: int
    prob_dangerous: float
    created_at: datetime = field(default_factory=datetime.utcnow)


class DataStore:
    """Maintain thread-safe, in-memory prediction and feedback records."""

    def __init__(self) -> None:
        """Initialize empty record collections and listener state."""
        self._lock = RLock()
        self._feedback: list[FeedbackEntry] = []
        self._predictions: dict[str, PredictionEntry] = {}
        self._listeners: list[Callable[[], None]] = []
        self.last_booking_id: str = ""

    def new_booking_id(self) -> str:
        """Create a booking identifier suitable for a new prediction.

        Returns:
            A booking identifier with the ``BK-`` prefix.
        """
        return f"BK-{uuid.uuid4().hex[:8].upper()}"

    def add_prediction(self, entry: PredictionEntry) -> None:
        """Store a prediction and notify subscribers.

        Args:
            entry: Prediction record to store.

        Raises:
            ValueError: If the booking identifier is already present.
        """
        with self._lock:
            if entry.booking_id in self._predictions:
                raise ValueError("Booking ID already exists.")
            self._predictions[entry.booking_id] = entry
            self.last_booking_id = entry.booking_id
        self._notify()

    def add_feedback(self, entry: FeedbackEntry) -> None:
        """Store feedback for a previously predicted booking.

        Args:
            entry: Feedback record to store.

        Raises:
            ValueError: If no prediction exists or feedback was already submitted.
        """
        with self._lock:
            if entry.booking_id not in self._predictions:
                raise ValueError("Booking ID not found. Predict first.")
            if any(f.booking_id == entry.booking_id for f in self._feedback):
                raise ValueError("Feedback already submitted for this Booking ID.")
            self._feedback.append(entry)
        self._notify()

    def all_feedback(self) -> list[FeedbackEntry]:
        """Return a snapshot of all feedback records.

        Returns:
            Feedback records in insertion order.
        """
        with self._lock:
            return list(self._feedback)

    def all_predictions(self) -> list[PredictionEntry]:
        """Return a snapshot of all prediction records.

        Returns:
            Prediction records in insertion order.
        """
        with self._lock:
            return list(self._predictions.values())

    def get_prediction(self, booking_id: str) -> PredictionEntry | None:
        """Look up a prediction by booking identifier.

        Args:
            booking_id: Identifier of the booking to find.

        Returns:
            The matching prediction, or ``None`` when it is absent.
        """
        with self._lock:
            return self._predictions.get(booking_id)

    def recent_booking_ids(self, limit: int = 10) -> list[str]:
        """Return the most recently stored booking identifiers.

        Args:
            limit: Maximum number of identifiers to return.

        Returns:
            Up to ``limit`` identifiers in insertion order.
        """
        with self._lock:
            return [p.booking_id for p in list(self._predictions.values())[-limit:]]

    def export_rows(self) -> list[dict[str, str]]:
        """Build exportable rows that pair feedback with predictions.

        Returns:
            String-valued rows for bookings with both prediction and feedback.
        """
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
        """Calculate aggregate prediction and feedback metrics.

        Returns:
            Counts and rates for feedback coverage, safety, ratings, and matches.
        """
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
        """Register a callback for store changes.

        Args:
            callback: Zero-argument function invoked after a stored change.

        Returns:
            A function that unregisters the callback.
        """
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
