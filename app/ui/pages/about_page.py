from __future__ import annotations

import os

import customtkinter as ctk

from app.ui.theme import Theme
from app.ui.widgets import Card, load_image, muted_label, pill, section_title


class AboutPage(ctk.CTkFrame):
    def __init__(self, master, _store=None):
        super().__init__(master, fg_color=Theme.COLORS["bg"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.images = {}

        wrap = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        wrap.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(wrap, fg_color=Theme.COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(header, text="About this App", font=Theme.font("h1"), text_color=Theme.COLORS["text"])
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Offline desktop tool for Practical AI CA2 (ST1508) trip safety predictions.",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text_muted"],
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.images["header"] = self._load_header_image("about.png")
        if self.images["header"] is not None:
            header_img = ctk.CTkLabel(header, image=self.images["header"], text="")
            header_img.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        content = ctk.CTkFrame(wrap, fg_color=Theme.COLORS["bg"])
        content.grid(row=1, column=0, sticky="nsew", pady=(18, 0))
        content.grid_columnconfigure((0, 1), weight=1)
        content.grid_rowconfigure(1, weight=1)

        left = Card(content)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        left.grid_columnconfigure(0, weight=1)

        section_title(left, "App Capabilities").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(left, "Core offline workflows.").grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        self._bullet(left, 2, "Real-time prediction for one sensor record.")
        self._bullet(left, 3, "Batch CSV prediction with export output.")
        self._bullet(left, 4, "Offline usage with no internet dependency.")
        self._bullet(left, 5, "Prediction generates a Booking ID for feedback matching.")

        right = Card(content)
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0), pady=(0, 12))
        right.grid_columnconfigure(0, weight=1)

        section_title(right, "Project Context").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(right, "Singapore Polytechnic DAAA coursework project.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 12)
        )

        self._bullet(right, 2, "Team: Goh Kun Ming, Goh Jenson, Liu Xingyu, Law Wei Tin.")
        self._bullet(right, 3, "Lecturer: Lecturer Liu Zheng.")
        self._bullet(right, 4, "Bundled model expects trip-level engineered features.")

        tip_card = Card(content)
        tip_card.grid(row=1, column=0, columnspan=2, sticky="nsew")
        tip_card.grid_columnconfigure(1, weight=1)

        tip_badge = pill(tip_card, "TIP", Theme.COLORS["accent"])
        tip_badge.grid(row=0, column=0, padx=16, pady=16, sticky="w")

        tip_text = ctk.CTkLabel(
            tip_card,
            text="This demo is for learning and portfolio review, not for real-world safety decisions.",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
            wraplength=720,
            justify="left",
        )
        tip_text.grid(row=0, column=1, padx=(6, 16), pady=16, sticky="w")

    def _bullet(self, master, row: int, text: str) -> None:
        label = ctk.CTkLabel(
            master,
            text=f"- {text}",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
            wraplength=420,
            justify="left",
        )
        label.grid(row=row, column=0, sticky="w", padx=20, pady=4)

    def _load_header_image(self, filename: str):
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        path = os.path.abspath(os.path.join(assets_dir, filename))
        return load_image(path, target=140)
