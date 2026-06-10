from __future__ import annotations

import csv
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from app.core.data_store import DataStore
from app.ui.theme import Theme
from app.ui.widgets import Card, load_image, muted_label, pill, section_title


class AdminPage(ctk.CTkFrame):
    def __init__(self, master, store: DataStore):
        super().__init__(master, fg_color=Theme.COLORS["bg"])
        self.store = store
        self._unsubscribe = self.store.subscribe(self.refresh)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.images = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(header, text="Admin Console", font=Theme.font("h1"), text_color=Theme.COLORS["text"])
        title.grid(row=0, column=0, sticky="w")

        desc = ctk.CTkLabel(
            header,
            text="Monitor feedback volume and basic drift signals (heuristic).",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text_muted"],
        )
        desc.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.images["header"] = self._load_header_image("admin.png")
        if self.images["header"] is not None:
            header_img = ctk.CTkLabel(header, image=self.images["header"], text="")
            header_img.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        body = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        body.grid_columnconfigure((0, 1), weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Summary cards
        self.card_stats = Card(body)
        self.card_stats.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        self.card_stats.grid_columnconfigure(0, weight=1)

        section_title(self.card_stats, "Feedback Stats").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(self.card_stats, "Updated from local feedback submissions.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 10)
        )

        self.total_label = ctk.CTkLabel(
            self.card_stats,
            text="Total feedback: 0",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.total_label.grid(row=2, column=0, sticky="w", padx=20, pady=4)

        self.pred_label = ctk.CTkLabel(
            self.card_stats,
            text="Total predictions: 0",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.pred_label.grid(row=3, column=0, sticky="w", padx=20, pady=4)

        self.cover_label = ctk.CTkLabel(
            self.card_stats,
            text="Feedback coverage: 0.0%",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.cover_label.grid(row=4, column=0, sticky="w", padx=20, pady=4)

        self.safe_label = ctk.CTkLabel(
            self.card_stats,
            text="Safe ratio: 0.0%",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.safe_label.grid(row=5, column=0, sticky="w", padx=20, pady=4)

        self.rating_label = ctk.CTkLabel(
            self.card_stats,
            text="Average rating: 0.0",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.rating_label.grid(row=6, column=0, sticky="w", padx=20, pady=4)

        self.match_label = ctk.CTkLabel(
            self.card_stats,
            text="Predicted vs actual match: 0.0%",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.match_label.grid(row=7, column=0, sticky="w", padx=20, pady=(4, 12))

        self.card_drift = Card(body)
        self.card_drift.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 12))
        self.card_drift.grid_columnconfigure(0, weight=1)

        section_title(self.card_drift, "Data Drift Monitor").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(self.card_drift, "Heuristic signals - replace with real drift tests later.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 10)
        )

        self.drift_badge = pill(self.card_drift, "LOW RISK", Theme.COLORS["good"])
        self.drift_badge.grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))

        self.drift_note = ctk.CTkLabel(
            self.card_drift,
            text="Not enough data to determine drift.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
            wraplength=340,
            justify="left",
        )
        self.drift_note.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 14))

        self.persist_note = ctk.CTkLabel(
            self.card_drift,
            text="Note: data is in-memory only. Add SQLite for persistence later.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
            wraplength=340,
            justify="left",
        )
        self.persist_note.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 12))

        # Recent feedback list
        self.card_recent = Card(body)
        self.card_recent.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.card_recent.grid_columnconfigure(0, weight=1)
        self.card_recent.grid_rowconfigure(2, weight=1)

        section_title(self.card_recent, "Recent Feedback").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(self.card_recent, "Most recent 5 submissions.").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        self.recent_box = ctk.CTkTextbox(
            self.card_recent,
            height=180,
            fg_color=Theme.COLORS["panel_2"],
            text_color=Theme.COLORS["text"],
            border_color=Theme.COLORS["border"],
            border_width=1,
        )
        self.recent_box.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.recent_box.configure(state="disabled")

        refresh_row = ctk.CTkFrame(self.card_recent, fg_color=Theme.COLORS["panel"])
        refresh_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        refresh_row.grid_columnconfigure(1, weight=1)

        self.updated_label = ctk.CTkLabel(
            refresh_row,
            text="Last updated: -",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.updated_label.grid(row=0, column=0, sticky="w", padx=12, pady=12)

        self.refresh_btn = ctk.CTkButton(
            refresh_row,
            text="Refresh",
            height=36,
            corner_radius=12,
            command=self.refresh,
        )
        self.refresh_btn.grid(row=0, column=2, padx=12, pady=12)

        self.export_btn = ctk.CTkButton(
            refresh_row,
            text="Export CSV",
            height=36,
            corner_radius=12,
            command=self.export_csv,
        )
        self.export_btn.grid(row=0, column=3, padx=(0, 12), pady=12)

        spark_wrap = ctk.CTkFrame(self.card_recent, fg_color=Theme.COLORS["panel"])
        spark_wrap.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 18))
        spark_wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            spark_wrap,
            text="Match Rate Trend",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))

        self.sparkline = tk.Canvas(
            spark_wrap,
            height=60,
            bg=Theme.COLORS["panel_2"],
            highlightthickness=1,
            highlightbackground=Theme.COLORS["border"],
        )
        self.sparkline.grid(row=1, column=0, sticky="ew", padx=12, pady=(6, 10))

        self.refresh()

    def refresh(self) -> None:
        stats = self.store.stats()
        total = int(stats["total"])
        total_predictions = int(stats["total_predictions"])
        feedback_rate = stats["feedback_rate"]
        safe_ratio = stats["safe_ratio"]
        avg_rating = stats["avg_rating"]
        match_rate = stats["match_rate"]

        self.total_label.configure(text=f"Total feedback: {total}")
        self.pred_label.configure(text=f"Total predictions: {total_predictions}")
        self.cover_label.configure(text=f"Feedback coverage: {feedback_rate * 100:.1f}%")
        self.safe_label.configure(text=f"Safe ratio: {safe_ratio * 100:.1f}%")
        self.rating_label.configure(text=f"Average rating: {avg_rating:.1f}")
        self.match_label.configure(text=f"Predicted vs actual match: {match_rate * 100:.1f}%")

        if total < 10:
            self.drift_badge.configure(text="LOW DATA", fg_color=Theme.COLORS["warn"])
            self.drift_note.configure(text="Need at least 10 submissions to check drift trends.")
        elif safe_ratio < 0.6 or avg_rating < 3.0 or match_rate < 0.7:
            self.drift_badge.configure(text="POTENTIAL DRIFT", fg_color=Theme.COLORS["warn"])
            self.drift_note.configure(
                text="Safe ratio or ratings dropped. Consider reviewing data quality or model behavior."
            )
        else:
            self.drift_badge.configure(text="LOW RISK", fg_color=Theme.COLORS["good"])
            self.drift_note.configure(text="Recent feedback looks stable based on heuristic thresholds.")

        recent = self.store.all_feedback()[-5:]
        lines = []
        for entry in reversed(recent):
            ts = entry.created_at.strftime("%Y-%m-%d %H:%M")
            safe_text = "SAFE" if entry.felt_safe else "UNSAFE"
            lines.append(f"[{ts}] {entry.booking_id} | {safe_text} | Rating {entry.rating}")
            if entry.notes:
                lines.append(f"  Notes: {entry.notes}")

        text = "\n".join(lines) if lines else "No feedback submitted yet."
        self.recent_box.configure(state="normal")
        self.recent_box.delete("1.0", "end")
        self.recent_box.insert("1.0", text)
        self.recent_box.configure(state="disabled")

        self.updated_label.configure(text=f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        self.after(50, self._draw_sparkline)

    def _load_header_image(self, filename: str):
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        path = os.path.abspath(os.path.join(assets_dir, filename))
        return load_image(path, target=140)

    def export_csv(self) -> None:
        rows = self.store.export_rows()
        if not rows:
            self.drift_badge.configure(text="INFO", fg_color=Theme.COLORS["warn"])
            self.drift_note.configure(text="No feedback to export yet.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Export admin report",
            defaultextension=".csv",
            initialfile="admin_report.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not save_path:
            return

        with open(save_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["booking_id", "predicted_label", "actual_label", "rating", "match"]
            )
            writer.writeheader()
            writer.writerows(rows)

        self.drift_badge.configure(text="EXPORTED", fg_color=Theme.COLORS["good"])
        self.drift_note.configure(text=f"Report saved to: {save_path}")

    def _draw_sparkline(self) -> None:
        self.sparkline.delete("all")
        width = max(1, self.sparkline.winfo_width())
        height = max(1, self.sparkline.winfo_height())
        feedback = self.store.all_feedback()
        if len(feedback) < 2:
            return

        points = []
        matched = 0
        for idx, f in enumerate(feedback, start=1):
            pred = self.store.get_prediction(f.booking_id)
            if pred is None:
                continue
            actual_label = 0 if f.felt_safe else 1
            if actual_label == pred.predicted_label:
                matched += 1
            rate = matched / idx
            points.append(rate)

        if not points:
            return

        step = width / max(1, (len(points) - 1))
        coords = []
        for i, rate in enumerate(points):
            x = i * step
            y = height - (rate * (height - 6)) - 3
            coords.extend([x, y])

        self.sparkline.create_line(
            *coords,
            fill=Theme.COLORS["accent"],
            width=2,
            smooth=True,
        )

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
