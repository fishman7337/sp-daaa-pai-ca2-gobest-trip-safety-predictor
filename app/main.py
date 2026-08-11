"""Desktop entry point for the Gobest trip safety predictor."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import customtkinter as ctk

from app.core.data_store import DataStore
from app.core.predictor import Predictor
from app.smoke import validate_distribution
from app.ui.pages.about_page import AboutPage
from app.ui.pages.admin_page import AdminPage
from app.ui.pages.batch_page import BatchPage
from app.ui.pages.feedback_page import FeedbackPage
from app.ui.pages.realtime_page import RealTimePage
from app.ui.theme import Theme


class App(ctk.CTk):
    """Gobest desktop application window."""

    def __init__(self) -> None:
        """Initialize the application window and its pages."""
        super().__init__()

        Theme.apply_global()

        self.title("Gobest Cab Trip Safety Predictor")
        self.geometry("1180x720")
        self.minsize(1020, 640)

        self.store = DataStore()
        self.current_page = "realtime"

        self._build_ui()

        self.show_page(self.current_page)

    def _build_ui(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        # Layout grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=Theme.COLORS["sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_rowconfigure(10, weight=1)  # push bottom section down
        self.sidebar.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkLabel(
            self.sidebar,
            text="Gobest Cab",
            font=Theme.font("title"),
        )
        brand.grid(row=0, column=0, padx=18, pady=(20, 0), sticky="w")

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Trip Safety Predictor\n(Offline Desktop App)",
            font=Theme.font("muted"),
            text_color=Theme.COLORS["text_muted"],
            justify="left",
        )
        subtitle.grid(row=1, column=0, padx=18, pady=(6, 18), sticky="w")

        self.nav_buttons = {}
        self._create_nav_button("Real-time", "realtime", row=2)
        self._create_nav_button("Batch CSV", "batch", row=3)
        self._create_nav_button("Trip Feedback", "feedback", row=4)
        self._create_nav_button("Admin Console", "admin", row=5)
        self._create_nav_button("About", "about", row=6)

        # Theme toggle
        self.theme_var = ctk.StringVar(value=Theme.MODE)
        theme_row = ctk.CTkFrame(self.sidebar, fg_color=Theme.COLORS["sidebar"])
        theme_row.grid(row=9, column=0, padx=18, pady=(10, 6), sticky="ew")
        theme_row.grid_columnconfigure(0, weight=1)

        theme_label = ctk.CTkLabel(
            theme_row,
            text="Theme",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        theme_label.grid(row=0, column=0, sticky="w")

        theme_switch = ctk.CTkSwitch(
            theme_row,
            text="Light mode",
            variable=self.theme_var,
            onvalue="light",
            offvalue="dark",
            command=self._on_theme_toggle,
        )
        theme_switch.grid(row=1, column=0, sticky="w", pady=(6, 0))
        if Theme.MODE == "light":
            theme_switch.select()
        else:
            theme_switch.deselect()

        # Bottom status / info
        self.model_status = ctk.CTkLabel(
            self.sidebar,
            text=f"Model: {Predictor.model_status()}",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.model_status.grid(row=11, column=0, padx=18, pady=(0, 6), sticky="w")

        self.footer = ctk.CTkLabel(
            self.sidebar,
            text="Practical AI CA2 (ST1508)",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.footer.grid(row=12, column=0, padx=18, pady=(0, 18), sticky="w")

        # Main container
        self.container = ctk.CTkFrame(self, corner_radius=0, fg_color=Theme.COLORS["bg"])
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        # Pages
        self.pages = {
            "realtime": RealTimePage(self.container, self.store),
            "batch": BatchPage(self.container, self.store),
            "feedback": FeedbackPage(self.container, self.store),
            "admin": AdminPage(self.container, self.store),
            "about": AboutPage(self.container, self.store),
        }
        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")

    def _on_theme_toggle(self) -> None:
        mode = self.theme_var.get()
        Theme.set_mode(mode)
        self._build_ui()
        self.show_page(self.current_page)

    def _create_nav_button(self, text: str, key: str, row: int) -> None:
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            command=lambda: self.show_page(key),
            height=42,
            corner_radius=12,
            anchor="w",
            fg_color=Theme.COLORS["sidebar"],
            hover_color=Theme.COLORS["button_hover"],
            text_color=Theme.COLORS["text_muted"],
            border_width=1,
            border_color=Theme.COLORS["sidebar"],
        )
        btn.grid(row=row, column=0, padx=14, pady=6, sticky="ew")
        self.nav_buttons[key] = btn

    def show_page(self, key: str) -> None:
        """Display one application page and update navigation styling.

        Args:
            key: Page identifier registered in ``self.pages``.

        """
        self.current_page = key
        # Visual active state
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(
                    fg_color=Theme.COLORS["button_active"],
                    hover_color=Theme.COLORS["button_active"],
                    text_color=Theme.COLORS["text"],
                    border_color=Theme.COLORS["accent"],
                )
            else:
                btn.configure(
                    fg_color=Theme.COLORS["sidebar"],
                    hover_color=Theme.COLORS["button_hover"],
                    text_color=Theme.COLORS["text_muted"],
                    border_color=Theme.COLORS["sidebar"],
                )

        self.pages[key].tkraise()


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Arguments to parse, excluding the executable name.

    Returns:
        Parsed application arguments.

    """
    parser = argparse.ArgumentParser(description="Gobest Cab Trip Safety Predictor")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="validate packaged resources and model inference without opening the GUI",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the desktop application or its non-interactive smoke test.

    Args:
        argv: Optional command-line arguments, excluding the executable name.

    Returns:
        Process exit code.

    """
    args = _parse_args(argv)
    if args.smoke_test:
        try:
            validate_distribution()
        except Exception as exc:  # pragma: no cover - exercised by packaged CI
            if sys.stderr is not None:
                print(f"Smoke test failed: {exc}", file=sys.stderr)
            return 1
        return 0

    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
