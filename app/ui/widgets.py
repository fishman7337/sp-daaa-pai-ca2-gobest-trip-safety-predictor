from __future__ import annotations

import logging
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from app.ui.theme import Theme

LOGGER = logging.getLogger(__name__)


class Card(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Theme.COLORS["panel"],
            border_color=Theme.COLORS["border"],
            border_width=1,
            corner_radius=16,
            **kwargs
        )


def section_title(master, text: str):
    return ctk.CTkLabel(master, text=text, font=Theme.font("h2"), text_color=Theme.COLORS["text"])


def muted_label(master, text: str):
    return ctk.CTkLabel(master, text=text, font=Theme.font("small"), text_color=Theme.COLORS["text_muted"])


def pill(master, text: str, color: str):
    return ctk.CTkLabel(
        master,
        text=text,
        fg_color=color,
        text_color="#081018",
        corner_radius=999,
        padx=10,
        pady=4,
        font=Theme.font("small"),
    )


class ToolTip:
    def __init__(self, widget, text: str, delay_ms: int = 400) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip = None
        self._after_id = None

        self._bind(self.widget)
        # Some customtkinter widgets keep their text label as a child; bind to it too.
        if hasattr(self.widget, "_text_label"):
            self._bind(self.widget._text_label)

    def _bind(self, target) -> None:
        target.bind("<Enter>", self._schedule, add="+")
        target.bind("<Leave>", self._hide, add="+")
        target.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                LOGGER.debug("Tooltip timer was already cancelled", exc_info=True)
            self._after_id = None

    def _show(self) -> None:
        if self.tip or not self.text:
            return

        self.tip = tk.Toplevel(self.widget)
        self.tip.withdraw()
        self.tip.wm_overrideredirect(True)
        self.tip.wm_attributes("-topmost", True)
        try:
            self.tip.transient(self.widget.winfo_toplevel())
        except tk.TclError:
            LOGGER.debug("Could not mark tooltip transient", exc_info=True)

        frame = tk.Frame(
            self.tip,
            bg=Theme.COLORS["panel_2"],
            highlightbackground=Theme.COLORS["border"],
            highlightthickness=1,
            bd=0,
        )
        label = tk.Label(
            frame,
            text=self.text,
            font=Theme.font("small"),
            fg=Theme.COLORS["text"],
            bg=Theme.COLORS["panel_2"],
            justify="left",
            wraplength=260,
        )
        label.pack(padx=10, pady=8)
        frame.pack()

        self.tip.update_idletasks()
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip.geometry(f"+{x}+{y}")
        self.tip.deiconify()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self.tip is not None:
            try:
                self.tip.destroy()
            except tk.TclError:
                LOGGER.debug("Tooltip window was already destroyed", exc_info=True)
            self.tip = None


def attach_tooltip(widget, text: str) -> None:
    widget._tooltip = ToolTip(widget, text=text)


def load_image(path: str, target: int = 160):
    try:
        image = Image.open(path)
    except OSError:
        LOGGER.warning("Could not load image asset: %s", path)
        return None
    width, height = image.size
    scale = min(target / max(1, width), target / max(1, height), 1.0)
    size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return ctk.CTkImage(light_image=image, dark_image=image, size=size)
