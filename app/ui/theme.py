"""Application color and typography theme definitions."""

from __future__ import annotations

import customtkinter as ctk


class Theme:
    """Centralized light and dark appearance settings."""

    _DARK = {
        "bg": "#0a0e14",
        "panel": "#0f1522",
        "panel_2": "#121b2b",
        "panel_3": "#101725",
        "border": "#1f2a3d",
        "text": "#e6edf7",
        "text_muted": "#a2b0c4",
        "accent": "#7ad7c1",
        "accent_2": "#5aa2ff",
        "good": "#3bd6a1",
        "warn": "#f5c542",
        "bad": "#ff7a7a",
        "button": "#121a2a",
        "button_hover": "#182339",
        "button_active": "#1f2f4a",
        "entry": "#0d1423",
        "sidebar": "#0b111b",
    }

    _LIGHT = {
        "bg": "#f6f7fb",
        "panel": "#ffffff",
        "panel_2": "#f0f2f7",
        "panel_3": "#e9edf5",
        "border": "#d7dbe6",
        "text": "#1b2230",
        "text_muted": "#5f6b7a",
        "accent": "#2da8a0",
        "accent_2": "#2f6fed",
        "good": "#1f9d77",
        "warn": "#d8901f",
        "bad": "#d84f4f",
        "button": "#eef1f7",
        "button_hover": "#e1e6f0",
        "button_active": "#d4dbe9",
        "entry": "#ffffff",
        "sidebar": "#eef1f7",
    }

    MODE = "dark"
    COLORS = dict(_DARK)

    @staticmethod
    def apply_global() -> None:
        """Apply the current appearance mode and base color theme."""
        ctk.set_appearance_mode(Theme.MODE)
        ctk.set_default_color_theme("blue")  # base theme; we still override colors manually

    @staticmethod
    def set_mode(mode: str) -> None:
        """Select the active light or dark palette.

        Args:
            mode: Requested appearance mode; values other than ``light`` use dark mode.

        """
        mode = mode.lower()
        Theme.MODE = "light" if mode == "light" else "dark"
        Theme.COLORS = dict(Theme._LIGHT if Theme.MODE == "light" else Theme._DARK)
        ctk.set_appearance_mode(Theme.MODE)

    @staticmethod
    def font(kind: str):
        """Return the configured system-font tuple for a semantic role.

        Args:
            kind: Font role such as ``title``, ``body``, or ``mono``.

        Returns:
            Tk-compatible font tuple.

        """
        # Use system fonts; keep it consistent
        if kind == "title":
            return ("Bahnschrift", 22, "bold")
        if kind == "h1":
            return ("Bahnschrift", 18, "bold")
        if kind == "h2":
            return ("Bahnschrift", 14, "bold")
        if kind == "body":
            return ("Bahnschrift", 12)
        if kind == "muted":
            return ("Bahnschrift", 12)
        if kind == "small":
            return ("Bahnschrift", 11)
        if kind == "mono":
            return ("Cascadia Mono", 11)
        return ("Bahnschrift", 12)
