"""Single-record trip-safety prediction page."""

from __future__ import annotations

import os

import customtkinter as ctk

from app.core.data_store import DataStore, PredictionEntry
from app.core.drift import DriftMonitor
from app.core.predictor import Predictor
from app.core.schema import FIELD_HELP, FIELD_LABELS, PREDICTION_SOURCE_TEXT, REQUIRED_FIELDS
from app.core.validation import safe_float, validate_numeric_inputs
from app.ui.theme import Theme
from app.ui.widgets import Card, attach_tooltip, load_image, muted_label, pill, section_title

FIELD_GROUPS = [
    ("Motion", "Speed, bearing, and time.", ["speed", "bearing", "second"]),
    ("Acceleration", "Linear acceleration per axis.", ["acceleration_x", "acceleration_y", "acceleration_z"]),
    ("Gyroscope", "Angular velocity per axis.", ["gyro_x", "gyro_y", "gyro_z"]),
    ("GPS Quality", "Location precision.", ["accuracy"]),
]


class RealTimePage(ctk.CTkFrame):
    """Interactive form for validating and scoring one sensor record."""

    def __init__(self, master, store: DataStore):
        """Initialize the real-time prediction page.

        Args:
            master: Parent Tk widget.
            store: Shared in-memory application data store.

        """
        super().__init__(master, fg_color=Theme.COLORS["bg"])
        self.predictor = Predictor()
        self.store = store
        self.drift = DriftMonitor(REQUIRED_FIELDS, reference_size=30, window_size=20, z_threshold=3.0)
        self.images = {}
        self.last_booking_id = ""

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header, text="Real-time Prediction", font=Theme.font("h1"), text_color=Theme.COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w")

        desc = ctk.CTkLabel(
            header,
            text="Enter one sensor record and predict trip risk instantly.",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text_muted"],
        )
        desc.grid(row=1, column=0, sticky="w", pady=(4, 0))

        model_row = ctk.CTkFrame(header, fg_color=Theme.COLORS["bg"])
        model_row.grid(row=2, column=0, sticky="w", pady=(8, 0))

        self.model_badge = pill(model_row, "MODEL", Theme.COLORS["accent"])
        self.model_badge.grid(row=0, column=0, sticky="w")
        self.model_version = ctk.CTkLabel(
            model_row,
            text=f"Status: {Predictor.model_status()}",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.model_version.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.images["header"] = self._load_header_image("realtime.png")
        if self.images["header"] is not None:
            header_img = ctk.CTkLabel(header, image=self.images["header"], text="")
            header_img.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        body = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        body.grid_columnconfigure(0, weight=2)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: input card
        self.card_inputs = Card(body)
        self.card_inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=0)
        self.card_inputs.grid_columnconfigure(0, weight=1)
        self.card_inputs.grid_rowconfigure(2, weight=1)

        section_title(self.card_inputs, "Sensor Inputs").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        ctk.CTkLabel(
            self.card_inputs,
            text="Units: m/s, m/s^2, rad/s, degrees, meters, seconds.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
            wraplength=430,
            justify="left",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        self.entries = {}
        input_scroll = ctk.CTkScrollableFrame(
            self.card_inputs,
            fg_color=Theme.COLORS["panel"],
            corner_radius=12,
            scrollbar_button_color=Theme.COLORS["button"],
            scrollbar_button_hover_color=Theme.COLORS["button_hover"],
        )
        input_scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        input_scroll.grid_columnconfigure((0, 1), weight=1)

        # Nice default values so demo looks good
        defaults = {
            "speed": "12.5",
            "acceleration_x": "0.4",
            "acceleration_y": "0.6",
            "acceleration_z": "9.7",
            "gyro_x": "0.12",
            "gyro_y": "0.10",
            "gyro_z": "0.08",
            "accuracy": "8.0",
            "bearing": "120.0",
            "second": "15",
        }

        for idx, (group_title, group_desc, fields) in enumerate(FIELD_GROUPS):
            r = idx // 2
            c = idx % 2

            group = ctk.CTkFrame(input_scroll, fg_color=Theme.COLORS["panel_2"], corner_radius=12)
            group.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
            group.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(group, text=group_title, font=Theme.font("h2"), text_color=Theme.COLORS["text"]).grid(
                row=0, column=0, sticky="w", padx=12, pady=(10, 0)
            )
            ctk.CTkLabel(
                group,
                text=group_desc,
                font=Theme.font("small"),
                text_color=Theme.COLORS["text_muted"],
                wraplength=170,
                justify="left",
            ).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 6))

            for f_idx, field in enumerate(fields):
                row = ctk.CTkFrame(group, fg_color=Theme.COLORS["panel_2"])
                row.grid(row=2 + f_idx, column=0, sticky="ew", padx=12, pady=(4, 8))
                row.grid_columnconfigure(0, weight=1)

                label = ctk.CTkLabel(
                    row,
                    text=FIELD_LABELS.get(field, field),
                    font=Theme.font("small"),
                    text_color=Theme.COLORS["text_muted"],
                )
                label.grid(row=0, column=0, sticky="w")

                help_icon = ctk.CTkLabel(
                    row,
                    text="?",
                    font=Theme.font("small"),
                    text_color=Theme.COLORS["accent"],
                )
                help_icon.grid(row=0, column=1, sticky="e")
                attach_tooltip(help_icon, FIELD_HELP.get(field, ""))

                ent = ctk.CTkEntry(
                    row,
                    height=32,
                    fg_color=Theme.COLORS["entry"],
                    border_color=Theme.COLORS["border"],
                    text_color=Theme.COLORS["text"],
                )
                ent.insert(0, defaults.get(field, "0"))
                ent.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
                self.entries[field] = ent

        btn_row = ctk.CTkFrame(self.card_inputs, fg_color=Theme.COLORS["panel"])
        btn_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 18))
        btn_row.grid_columnconfigure(0, weight=1)

        self.btn_predict = ctk.CTkButton(
            btn_row,
            text="Predict Risk",
            height=42,
            corner_radius=12,
            command=self.on_predict,
        )
        self.btn_predict.grid(row=0, column=0, sticky="ew")

        self.status = ctk.CTkLabel(
            btn_row,
            text="Ready.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.status.grid(row=1, column=0, sticky="w", pady=(8, 0))

        # Right: result card
        self.card_result = Card(body)
        self.card_result.grid(row=0, column=1, sticky="nsew", padx=(16, 0), pady=0)
        self.card_result.grid_columnconfigure(0, weight=1)

        section_title(self.card_result, "Result").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(self.card_result, "Predicted class and probability.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 12)
        )

        self.badge_row = ctk.CTkFrame(self.card_result, fg_color=Theme.COLORS["panel"])
        self.badge_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.badge_row.grid_columnconfigure(0, weight=1)

        self.badge = pill(self.badge_row, "SAFE", Theme.COLORS["good"])
        self.badge.grid(row=0, column=0, sticky="w", pady=10)

        self.result_value = ctk.CTkLabel(
            self.card_result,
            text="Safe",
            font=Theme.font("title"),
            text_color=Theme.COLORS["good"],
        )
        self.result_value.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 4))

        self.prob_value = ctk.CTkLabel(
            self.card_result,
            text="Dangerous probability: 0.0%",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.prob_value.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 8))

        self.source_value = ctk.CTkLabel(
            self.card_result,
            text="Prediction source: -",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.source_value.grid(row=5, column=0, sticky="w", padx=20, pady=(0, 8))

        self.prob_bar = ctk.CTkProgressBar(
            self.card_result,
            height=12,
            corner_radius=8,
            fg_color=Theme.COLORS["panel_3"],
            progress_color=Theme.COLORS["bad"],
        )
        self.prob_bar.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.prob_bar.set(0.0)

        booking_row = ctk.CTkFrame(self.card_result, fg_color=Theme.COLORS["panel"])
        booking_row.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 8))
        booking_row.grid_columnconfigure(0, weight=1)

        self.booking_label = ctk.CTkLabel(
            booking_row,
            text="Booking ID: -",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.booking_label.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=8)

        self.copy_btn = ctk.CTkButton(
            booking_row,
            text="Copy",
            height=28,
            width=70,
            corner_radius=10,
            command=self.copy_booking_id,
        )
        self.copy_btn.grid(row=0, column=1, sticky="e", padx=(6, 12), pady=6)

        self.note = ctk.CTkLabel(
            self.card_result,
            text="Enter inputs and click Predict Risk to see a result.",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text_muted"],
            wraplength=260,
            justify="left",
        )
        self.note.grid(row=8, column=0, sticky="w", padx=20, pady=(0, 16))

        self.drift_label = ctk.CTkLabel(
            self.card_result,
            text="Drift: collecting baseline.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
            wraplength=260,
            justify="left",
        )
        self.drift_label.grid(row=9, column=0, sticky="w", padx=20, pady=(0, 12))

        # Placeholder panel
        explain = ctk.CTkFrame(self.card_result, fg_color=Theme.COLORS["panel_2"], corner_radius=14)
        explain.grid(row=10, column=0, sticky="nsew", padx=20, pady=(0, 18))
        explain.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(explain, text="Model Notes", font=Theme.font("h2"), text_color=Theme.COLORS["text"]).grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4)
        )
        ctk.CTkLabel(
            explain,
            text="Single-record inputs use the fallback when the model needs trip-level engineered features.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
            justify="left",
            wraplength=520,
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

    def on_predict(self) -> None:
        """Validate form values, run inference, and store the prediction."""
        raw = {k: self.entries[k].get() for k in REQUIRED_FIELDS}
        v = validate_numeric_inputs(raw)
        if not v.ok:
            self.status.configure(text=f"Error: {v.message}", text_color=Theme.COLORS["bad"])
            return

        x = {k: safe_float(raw[k], 0.0) for k in REQUIRED_FIELDS}
        pred = self.predictor.predict_one(x)

        report = self.drift.update(x)

        booking_id = self.store.new_booking_id()
        entry = PredictionEntry(
            booking_id=booking_id,
            predicted_label=pred.label,
            prob_dangerous=pred.prob_dangerous,
        )
        self.store.add_prediction(entry)
        self.last_booking_id = booking_id

        # Update UI
        is_dangerous = pred.label == 1
        badge_color = Theme.COLORS["bad"] if is_dangerous else Theme.COLORS["good"]
        label_text = "DANGEROUS" if is_dangerous else "SAFE"

        self.badge.configure(text=label_text, fg_color=badge_color)
        self.result_value.configure(text=label_text.title(), text_color=badge_color)

        prob = float(pred.prob_dangerous)
        self.prob_value.configure(text=f"Dangerous probability: {prob * 100:.1f}%")
        source_text = PREDICTION_SOURCE_TEXT.get(pred.source, pred.source)
        self.source_value.configure(text=f"Prediction source: {source_text}")
        self.prob_bar.configure(progress_color=badge_color)
        self.prob_bar.set(prob)

        self.note.configure(text=pred.message)

        drift_color = Theme.COLORS["text_muted"]
        if report.ref_ready and report.window_ready and report.drifted:
            drift_color = Theme.COLORS["warn"]
        self.drift_label.configure(text=f"Drift: {report.message}", text_color=drift_color)
        self.booking_label.configure(text=f"Booking ID: {booking_id}")
        self.status.configure(text="OK. Prediction complete.", text_color=Theme.COLORS["good"])

    def copy_booking_id(self) -> None:
        """Copy the latest booking identifier to the system clipboard."""
        if not self.last_booking_id:
            self.status.configure(text="No Booking ID to copy yet.", text_color=Theme.COLORS["warn"])
            return
        self.clipboard_clear()
        self.clipboard_append(self.last_booking_id)
        self.status.configure(text="Booking ID copied.", text_color=Theme.COLORS["good"])

    def _load_header_image(self, filename: str):
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        path = os.path.abspath(os.path.join(assets_dir, filename))
        return load_image(path, target=140)
