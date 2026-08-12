"""Trip-feedback collection page."""

from __future__ import annotations

import os

import customtkinter as ctk

from app.core.data_store import DataStore, FeedbackEntry
from app.ui.theme import Theme
from app.ui.widgets import Card, load_image, muted_label, pill, section_title


class FeedbackPage(ctk.CTkFrame):
    """Page for linking rider feedback to stored predictions."""

    def __init__(self, master, store: DataStore):
        """Initialize the feedback form.

        Args:
            master: Parent Tk widget.
            store: Shared in-memory application data store.

        """
        super().__init__(master, fg_color=Theme.COLORS["bg"])
        self.store = store
        self.images = {}
        self._unsubscribe = self.store.subscribe(self.refresh_booking_ids)
        self.bind("<Destroy>", self._on_destroy, add="+")

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(header, text="Trip Feedback", font=Theme.font("h1"), text_color=Theme.COLORS["text"])
        title.grid(row=0, column=0, sticky="w")

        desc = ctk.CTkLabel(
            header,
            text="Collect driver and rider feedback to compare predicted vs actual.",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text_muted"],
        )
        desc.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.images["header"] = self._load_header_image("feedback.png")
        if self.images["header"] is not None:
            header_img = ctk.CTkLabel(header, image=self.images["header"], text="")
            header_img.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        body = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        section_title(card, "Feedback Form").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(card, "Required fields are marked with *.").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        form = ctk.CTkFrame(card, fg_color=Theme.COLORS["panel"])
        form.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 16))
        form.grid_columnconfigure(0, weight=1)

        # Booking ID
        ctk.CTkLabel(form, text="Booking ID *", font=Theme.font("small"), text_color=Theme.COLORS["text_muted"]).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 4)
        )
        self.booking_entry = ctk.CTkEntry(
            form,
            height=32,
            fg_color=Theme.COLORS["entry"],
            border_color=Theme.COLORS["border"],
            text_color=Theme.COLORS["text"],
        )
        self.booking_entry.grid(row=1, column=0, sticky="ew", padx=16)

        self.booking_help = ctk.CTkLabel(
            form,
            text="Use the Booking ID generated after prediction.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.booking_help.grid(row=2, column=0, sticky="w", padx=16, pady=(6, 0))

        select_row = ctk.CTkFrame(form, fg_color=Theme.COLORS["panel"])
        select_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 0))
        select_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            select_row,
            text="Recent Booking IDs",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w")

        self.recent_menu = ctk.CTkOptionMenu(
            select_row,
            values=["-"],
            fg_color=Theme.COLORS["panel_2"],
            button_color=Theme.COLORS["button"],
            button_hover_color=Theme.COLORS["button_hover"],
            text_color=Theme.COLORS["text"],
            command=self._on_recent_selected,
        )
        self.recent_menu.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # Felt safe
        ctk.CTkLabel(form, text="Felt Safe? *", font=Theme.font("small"), text_color=Theme.COLORS["text_muted"]).grid(
            row=4, column=0, sticky="w", padx=16, pady=(14, 4)
        )
        self.safe_choice = ctk.CTkSegmentedButton(
            form,
            values=["Yes", "No"],
            fg_color=Theme.COLORS["panel_2"],
            selected_color=Theme.COLORS["accent"],
            selected_hover_color=Theme.COLORS["accent"],
            text_color=Theme.COLORS["text"],
        )
        self.safe_choice.set("Yes")
        self.safe_choice.grid(row=5, column=0, sticky="w", padx=16)

        # Rating
        ctk.CTkLabel(
            form, text="Trip Rating (1-5) *", font=Theme.font("small"), text_color=Theme.COLORS["text_muted"]
        ).grid(row=6, column=0, sticky="w", padx=16, pady=(14, 4))
        self.rating_choice = ctk.CTkOptionMenu(
            form,
            values=["1", "2", "3", "4", "5"],
            fg_color=Theme.COLORS["panel_2"],
            button_color=Theme.COLORS["button"],
            button_hover_color=Theme.COLORS["button_hover"],
            text_color=Theme.COLORS["text"],
        )
        self.rating_choice.set("5")
        self.rating_choice.grid(row=7, column=0, sticky="w", padx=16)

        # Notes
        ctk.CTkLabel(
            form, text="Additional Notes", font=Theme.font("small"), text_color=Theme.COLORS["text_muted"]
        ).grid(row=8, column=0, sticky="w", padx=16, pady=(14, 4))
        self.notes = ctk.CTkTextbox(
            form,
            height=120,
            fg_color=Theme.COLORS["panel_2"],
            text_color=Theme.COLORS["text"],
            border_color=Theme.COLORS["border"],
            border_width=1,
        )
        self.notes.grid(row=9, column=0, sticky="nsew", padx=16, pady=(0, 14))

        action_row = ctk.CTkFrame(card, fg_color=Theme.COLORS["panel"])
        action_row.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))
        action_row.grid_columnconfigure(1, weight=1)

        self.badge = pill(action_row, "IDLE", Theme.COLORS["warn"])
        self.badge.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=12)

        self.status = ctk.CTkLabel(
            action_row,
            text="Fill in the form and submit feedback.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.status.grid(row=0, column=1, sticky="w")

        self.submit_btn = ctk.CTkButton(
            action_row,
            text="Submit Feedback",
            height=40,
            corner_radius=12,
            command=self.on_submit,
        )
        self.submit_btn.grid(row=0, column=2, padx=12, pady=12)

        self.predicted_label = ctk.CTkLabel(
            action_row,
            text="Prediction: -",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.predicted_label.grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))

        self.booking_entry.bind("<FocusIn>", self._autofill_from_clipboard, add="+")
        self.refresh_booking_ids()

    def on_submit(self) -> None:
        """Validate and store the current feedback form."""
        booking_id = self.booking_entry.get().strip()
        if not booking_id:
            self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
            self.status.configure(text="Booking ID is required.", text_color=Theme.COLORS["bad"])
            return

        pred = self.store.get_prediction(booking_id)
        if pred is None:
            self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
            self.status.configure(text="Booking ID not found. Predict first.", text_color=Theme.COLORS["bad"])
            return

        felt_safe = self.safe_choice.get() == "Yes"
        rating = int(self.rating_choice.get())
        notes = self.notes.get("1.0", "end").strip()

        entry = FeedbackEntry(
            booking_id=booking_id,
            felt_safe=felt_safe,
            rating=rating,
            notes=notes,
        )
        try:
            self.store.add_feedback(entry)
        except ValueError as exc:
            self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
            self.status.configure(text=str(exc), text_color=Theme.COLORS["bad"])
            return

        self.badge.configure(text="SAVED", fg_color=Theme.COLORS["good"])
        self.status.configure(text="Feedback saved locally.", text_color=Theme.COLORS["good"])
        self.predicted_label.configure(
            text=f"Prediction: {'DANGEROUS' if pred.predicted_label == 1 else 'SAFE'} ({pred.prob_dangerous:.2f})"
        )

        self.booking_entry.delete(0, "end")
        self.safe_choice.set("Yes")
        self.rating_choice.set("5")
        self.notes.delete("1.0", "end")

    def _load_header_image(self, filename: str):
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        path = os.path.abspath(os.path.join(assets_dir, filename))
        return load_image(path, target=140)

    def refresh_booking_ids(self) -> None:
        """Refresh the recent-booking selector from the shared store."""
        ids = self.store.recent_booking_ids()
        menu_values = ids if ids else ["-"]
        self.recent_menu.configure(values=menu_values)
        if ids:
            self.recent_menu.set(ids[-1])
            if not self.booking_entry.get().strip():
                self.booking_entry.insert(0, ids[-1])
        elif not self.booking_entry.get().strip() and self.store.last_booking_id:
            self.booking_entry.insert(0, self.store.last_booking_id)

    def _on_recent_selected(self, value: str) -> None:
        if value and value != "-":
            self.booking_entry.delete(0, "end")
            self.booking_entry.insert(0, value)

    def _autofill_from_clipboard(self, _event=None) -> None:
        try:
            clip = self.clipboard_get().strip()
        except Exception:
            return
        if clip.startswith("BK-") and self.store.get_prediction(clip) is not None:
            self.booking_entry.delete(0, "end")
            self.booking_entry.insert(0, clip)

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
