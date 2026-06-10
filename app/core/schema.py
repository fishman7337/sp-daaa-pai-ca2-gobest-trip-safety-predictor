from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    """Input-field metadata shared by validation, preprocessing, and the UI."""

    name: str
    label: str
    help_text: str
    min_value: float | None = None
    max_value: float | None = None


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("speed", "Speed", "Vehicle speed in meters per second (m/s)."),
    FieldSpec("acceleration_x", "Acceleration X", "Acceleration on the X axis (m/s^2)."),
    FieldSpec("acceleration_y", "Acceleration Y", "Acceleration on the Y axis (m/s^2)."),
    FieldSpec("acceleration_z", "Acceleration Z", "Acceleration on the Z axis (m/s^2)."),
    FieldSpec("gyro_x", "Gyroscope X", "Angular velocity on the X axis (rad/s)."),
    FieldSpec("gyro_y", "Gyroscope Y", "Angular velocity on the Y axis (rad/s)."),
    FieldSpec("gyro_z", "Gyroscope Z", "Angular velocity on the Z axis (rad/s)."),
    FieldSpec("accuracy", "GPS Accuracy", "GPS accuracy radius in meters.", min_value=0.0),
    FieldSpec("bearing", "Bearing", "Heading in degrees (0 to 360).", min_value=0.0, max_value=360.0),
    FieldSpec("second", "Second", "Seconds since trip start.", min_value=0.0),
)

REQUIRED_FIELDS = [spec.name for spec in FIELD_SPECS]
FIELD_LABELS = {spec.name: spec.label for spec in FIELD_SPECS}
FIELD_HELP = {spec.name: spec.help_text for spec in FIELD_SPECS}
FIELD_LIMITS = {spec.name: (spec.min_value, spec.max_value) for spec in FIELD_SPECS}

FIELD_ALIASES = {
    "bookingid": "booking_id",
    "accuracy_m": "accuracy",
    "bearing_deg": "bearing",
}

LABEL_TEXT = {
    0: "SAFE",
    1: "DANGEROUS",
}

PREDICTION_SOURCE_TEXT = {
    "model": "Decision-tree model",
    "heuristic_fallback": "Heuristic fallback",
}
