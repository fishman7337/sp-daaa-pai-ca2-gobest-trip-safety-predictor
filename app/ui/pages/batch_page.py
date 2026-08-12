"""Batch CSV prediction and export page."""

from __future__ import annotations

import math
import os
import queue
import tempfile
import threading
from tkinter import TclError, filedialog, ttk
from tkinter import font as tkfont

import customtkinter as ctk
import pandas as pd

from app.core.batch import run_batch
from app.core.data_store import DataStore, PredictionEntry
from app.core.drift import DriftMonitor
from app.core.predictor import Predictor
from app.core.schema import REQUIRED_FIELDS
from app.ui.theme import Theme
from app.ui.widgets import Card, load_image, muted_label, pill, section_title


class BatchPage(ctk.CTkFrame):
    """Page for loading, scoring, previewing, and exporting trip CSV data."""

    def __init__(self, master, store: DataStore):
        """Initialize the batch-prediction page.

        Args:
            master: Parent Tk widget.
            store: Shared in-memory application data store.

        """
        super().__init__(master, fg_color=Theme.COLORS["bg"])
        self.predictor = Predictor()
        self.csv_path: str | None = None
        self.df_preview: pd.DataFrame | None = None
        self.images = {}
        self.store = store
        self.drift = DriftMonitor(REQUIRED_FIELDS, reference_size=40, window_size=20, z_threshold=3.0)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        title = ctk.CTkLabel(
            header, text="Batch CSV Prediction", font=Theme.font("h1"), text_color=Theme.COLORS["text"]
        )
        title.grid(row=0, column=0, sticky="w")

        desc = ctk.CTkLabel(
            header,
            text="Upload a CSV file, predict all rows, then export a new CSV with results.",
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
            text=f"Version: {Predictor.model_status()}",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.model_version.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.images["header"] = self._load_header_image("batch.png")
        if self.images["header"] is not None:
            header_img = ctk.CTkLabel(header, image=self.images["header"], text="")
            header_img.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        body = ctk.CTkFrame(self, fg_color=Theme.COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Controls Card
        control = Card(body)
        control.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        control.grid_columnconfigure(0, weight=1)

        section_title(control, "Batch Controls").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(control, "Your CSV must contain the required sensor columns.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 10)
        )

        file_card = ctk.CTkFrame(control, fg_color=Theme.COLORS["panel_2"], corner_radius=12)
        file_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))
        file_card.grid_columnconfigure(0, weight=1)

        self.file_name = ctk.CTkLabel(
            file_card,
            text="No file selected",
            font=Theme.font("body"),
            text_color=Theme.COLORS["text"],
        )
        self.file_name.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 2))

        self.file_meta = ctk.CTkLabel(
            file_card,
            text="Upload a CSV to begin.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.file_meta.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

        btns = ctk.CTkFrame(control, fg_color=Theme.COLORS["panel"])
        btns.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 12))
        btns.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_upload = ctk.CTkButton(btns, text="Upload CSV", height=40, corner_radius=12, command=self.on_upload)
        self.btn_upload.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.btn_run = ctk.CTkButton(btns, text="Run Prediction", height=40, corner_radius=12, command=self.on_run)
        self.btn_run.grid(row=0, column=1, sticky="ew", padx=10)

        self.btn_export = ctk.CTkButton(btns, text="Export Output", height=40, corner_radius=12, command=self.on_export)
        self.btn_export.grid(row=0, column=2, sticky="ew", padx=(10, 0))

        progress_row = ctk.CTkFrame(control, fg_color=Theme.COLORS["panel"])
        progress_row.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))
        progress_row.grid_columnconfigure(0, weight=1)

        self.progress_label = ctk.CTkLabel(
            progress_row,
            text="Status: idle",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.progress_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.progress = ctk.CTkProgressBar(progress_row)
        self.progress.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.progress.set(0)

        # Summary strip
        self.summary_row = ctk.CTkFrame(control, fg_color=Theme.COLORS["panel"])
        self.summary_row.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 18))
        self.summary_row.grid_columnconfigure(1, weight=1)

        self.badge = pill(self.summary_row, "IDLE", Theme.COLORS["warn"])
        self.badge.grid(row=0, column=0, sticky="w", pady=10, padx=(12, 0))

        self.summary = ctk.CTkLabel(
            self.summary_row,
            text="Upload a CSV to begin.",
            font=Theme.font("small"),
            text_color=Theme.COLORS["text_muted"],
        )
        self.summary.grid(row=0, column=1, sticky="w", padx=10)

        # Preview Card
        preview = Card(body)
        preview.grid(row=1, column=0, sticky="nsew")
        preview.grid_rowconfigure(2, weight=1)
        preview.grid_columnconfigure(0, weight=1)

        section_title(preview, "Preview").grid(row=0, column=0, sticky="w", padx=20, pady=(16, 2))
        muted_label(preview, "Shows the first 15 rows after prediction.").grid(
            row=1, column=0, sticky="w", padx=20, pady=(0, 10)
        )

        # Treeview (ttk) inside CTkFrame
        self.table_container = ctk.CTkFrame(preview, fg_color=Theme.COLORS["panel"])
        self.table_container.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 18))
        self.table_container.grid_rowconfigure(0, weight=1)
        self.table_container.grid_columnconfigure(0, weight=1)

        self.tree = None
        self._tree_font = tkfont.Font(font=Theme.font("small"))
        self._tree_font_bold = tkfont.Font(font=("Bahnschrift", 11, "bold"))
        self._init_treeview()

        self.output_path: str | None = None
        self._run_thread: threading.Thread | None = None
        self._run_queue: queue.Queue[tuple[str, object]] | None = None

    def _load_header_image(self, filename: str):
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        path = os.path.abspath(os.path.join(assets_dir, filename))
        return load_image(path, target=140)

    def _init_treeview(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except TclError:
            pass

        style.configure(
            "Treeview",
            background=Theme.COLORS["panel_2"],
            fieldbackground=Theme.COLORS["panel_2"],
            foreground=Theme.COLORS["text"],
            rowheight=28,
            bordercolor=Theme.COLORS["border"],
            borderwidth=0,
            font=Theme.font("small"),
        )
        style.configure(
            "Treeview.Heading",
            background=Theme.COLORS["panel"],
            foreground=Theme.COLORS["text_muted"],
            font=("Bahnschrift", 11, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", Theme.COLORS["button_active"])])

        self.tree = ttk.Treeview(self.table_container, columns=(), show="headings", height=10)
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(self.table_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=0, column=1, sticky="ns")

        xscroll = ttk.Scrollbar(self.table_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=xscroll.set)
        xscroll.grid(row=1, column=0, sticky="ew")

        self.tree.tag_configure("odd", background=Theme.COLORS["panel_2"])
        self.tree.tag_configure("even", background=Theme.COLORS["panel_3"])

    def _format_value(self, value):
        if isinstance(value, float):
            if math.isnan(value):
                return ""
            return f"{value:.3f}"
        return value

    def _populate_preview(self, df: pd.DataFrame) -> None:
        if self.tree is None:
            return

        for col in self.tree["columns"]:
            self.tree.heading(col, text="")
        self.tree.delete(*self.tree.get_children())

        cols = list(df.columns)
        self.tree["columns"] = cols

        sample_rows = df.head(30).itertuples(index=False)
        col_widths = {c: self._tree_font.measure(c) + 18 for c in cols}

        for row in sample_rows:
            for c, v in zip(cols, row, strict=False):
                v_str = str(self._format_value(v))
                col_widths[c] = max(col_widths[c], self._tree_font.measure(v_str) + 18)

        for c in cols:
            self.tree.heading(c, text=c)
            anchor = "e" if c.startswith(("avg_", "prob_", "n_samples")) else "w"
            self.tree.column(c, width=min(col_widths[c], 260), anchor=anchor, stretch=False)

        for idx, row in enumerate(df.itertuples(index=False)):
            tag = "even" if idx % 2 == 0 else "odd"
            values = [self._format_value(v) for v in row]
            self.tree.insert("", "end", values=values, tags=(tag,))

    def _format_bytes(self, value: int) -> str:
        size = float(value)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def on_upload(self) -> None:
        """Prompt for a CSV file and prepare it for prediction."""
        path = filedialog.askopenfilename(
            title="Select CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        self.csv_path = path
        file_name = os.path.basename(path)
        size = self._format_bytes(os.path.getsize(path))
        self.file_name.configure(text=file_name)
        self.file_meta.configure(text=f"Size: {size} | Ready to run prediction.")
        self.badge.configure(text="READY", fg_color=Theme.COLORS["good"])
        self.summary.configure(text="File loaded. Click Run Prediction.")
        self.progress_label.configure(text="Status: ready")
        self.progress.set(0)
        self.output_path = None

    def on_run(self) -> None:
        """Start batch inference in a background worker."""
        if not self.csv_path:
            self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
            self.summary.configure(text="Please upload a CSV first.")
            self.progress_label.configure(text="Status: error")
            return

        self.badge.configure(text="RUNNING", fg_color=Theme.COLORS["warn"])
        self.summary.configure(text="Predicting... (running in background)")
        self.progress_label.configure(text="Status: running")
        self.progress.set(0.2)
        self.update_idletasks()
        self.btn_run.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.btn_upload.configure(state="disabled")

        out_dir = os.path.dirname(self.csv_path)
        tmp = tempfile.NamedTemporaryFile(
            prefix="gobest_predictions_",
            suffix=".csv",
            dir=out_dir,
            delete=False,
        )
        tmp.close()
        self.output_path = tmp.name

        self._run_queue = queue.Queue()
        self._run_thread = threading.Thread(target=self._run_batch_worker, daemon=True)
        self._run_thread.start()
        self.after(100, self._poll_run_queue)

    def _run_batch_worker(self) -> None:
        try:
            res, df_out = run_batch(
                self.predictor,
                self.csv_path,
                self.output_path,
                store=None,
                return_df=True,
            )
            if df_out is None:
                df_out = pd.read_csv(self.output_path)
            prediction_records = self._prediction_records(df_out)
            df_preview = self._load_preview_mix(df_out, nrows=15)
            if all(field in df_preview.columns for field in REQUIRED_FIELDS):
                drift_message = self.drift.analyze_dataframe(df_preview).message
            else:
                drift_message = "Drift check skipped for engineered batch output."
            if self._run_queue is not None:
                self._run_queue.put(("success", (res, df_preview, drift_message, prediction_records)))
        except Exception as exc:
            if self._run_queue is not None:
                self._run_queue.put(("error", exc))

    def _poll_run_queue(self) -> None:
        if self._run_queue is None:
            return
        try:
            status, payload = self._run_queue.get_nowait()
        except queue.Empty:
            if self._run_thread is not None and self._run_thread.is_alive():
                self.after(100, self._poll_run_queue)
            return

        self._run_queue = None
        if status == "success":
            res, df_preview, drift_message, prediction_records = payload
            self._on_run_success(res, df_preview, drift_message, prediction_records)
        else:
            self._on_run_error(payload)

    def _on_run_success(self, res, df_preview, drift_message, prediction_records) -> None:
        self._register_predictions(prediction_records)
        self.df_preview = df_preview
        self._populate_preview(self.df_preview)
        self.progress.set(1.0)
        self.badge.configure(text="DONE", fg_color=Theme.COLORS["good"])
        self.summary.configure(text=f"Rows: {res.rows} | Dangerous: {res.dangerous_count} | {drift_message}")
        self.progress_label.configure(text="Status: complete")
        self.btn_run.configure(state="normal")
        self.btn_export.configure(state="normal")
        self.btn_upload.configure(state="normal")

    def _on_run_error(self, error: Exception) -> None:
        self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
        self.summary.configure(text=str(error))
        self.progress_label.configure(text="Status: error")
        self.progress.set(0)
        self.btn_run.configure(state="normal")
        self.btn_export.configure(state="normal")
        self.btn_upload.configure(state="normal")

    def _load_preview_mix(self, data: str | pd.DataFrame, nrows: int = 15) -> pd.DataFrame:
        # Pull a reasonable slice to mix safe/dangerous without loading the whole file.
        df = pd.read_csv(data, nrows=2000) if isinstance(data, str) else data.head(2000).copy()
        if df.empty:
            return df

        if "pred_label" not in df.columns:
            return df.head(nrows)

        # Only drop rows missing prediction outputs to avoid wiping rows with feature NaNs.
        df = df.dropna(subset=["pred_label", "prob_dangerous"], how="any")
        # Hide columns that are entirely NaN in the preview, and fill remaining NaNs for display.
        df = df.dropna(axis=1, how="all")
        float_cols = df.select_dtypes(include=["float", "float64", "float32"]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].round(3)

        safe = df[df["pred_label"] == 0].head(nrows)
        danger = df[df["pred_label"] == 1].head(nrows)
        half = max(1, nrows // 2)
        selected = pd.concat([safe.head(half), danger.head(half)])
        selected_indices = set(selected.index)
        mix = selected.copy()
        if len(mix) < nrows:
            extra = df[~df.index.isin(selected_indices)].head(nrows - len(mix))
            mix = pd.concat([mix, extra])
        mix = mix.head(nrows).copy()
        mix = mix.reset_index(drop=True)
        mix = mix.fillna("")
        if "pred_label" in mix.columns:
            mix["pred_label"] = mix["pred_label"].map({0: "SAFE", 1: "DANGEROUS"}).fillna(mix["pred_label"])

        priority = [c for c in ["booking_id", "app_booking_id", "pred_label", "prob_dangerous"] if c in mix.columns]
        avg_cols = [c for c in mix.columns if c.startswith("avg_")]
        count_cols = [c for c in ["n_samples_raw"] if c in mix.columns]
        remaining = [c for c in mix.columns if c not in priority + avg_cols + count_cols and not c.startswith("fe_")]
        if avg_cols or count_cols:
            mix = mix[priority + count_cols + avg_cols + remaining]
        else:
            mix = mix[priority + remaining]
        return mix

    def _prediction_records(self, df: pd.DataFrame) -> list[tuple[str, int, float]]:
        records: list[tuple[str, int, float]] = []
        for _, row in df.iterrows():
            booking_id = row.get("booking_id")
            if pd.isna(booking_id) or str(booking_id).strip() == "":
                booking_id = self.store.new_booking_id()
            records.append(
                (
                    str(booking_id),
                    int(row.get("pred_label", 0)),
                    float(row.get("prob_dangerous", 0.0)),
                )
            )
        return records

    def _register_predictions(self, records: list[tuple[str, int, float]]) -> None:
        for booking_id, label, probability in records:
            try:
                self.store.add_prediction(
                    PredictionEntry(
                        booking_id=booking_id,
                        predicted_label=label,
                        prob_dangerous=probability,
                    )
                )
            except ValueError:
                self.store.add_prediction(
                    PredictionEntry(
                        booking_id=self.store.new_booking_id(),
                        predicted_label=label,
                        prob_dangerous=probability,
                    )
                )

    def on_export(self) -> None:
        """Prompt for a destination and copy the generated prediction CSV."""
        if not self.output_path:
            self.badge.configure(text="INFO", fg_color=Theme.COLORS["warn"])
            self.summary.configure(text="Run prediction first to generate output.")
            self.progress_label.configure(text="Status: waiting")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save output CSV as",
            defaultextension=".csv",
            initialfile="predictions_output.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not save_path:
            return

        try:
            with open(self.output_path, "rb") as fsrc:
                data = fsrc.read()
            with open(save_path, "wb") as fdst:
                fdst.write(data)

            self.badge.configure(text="EXPORTED", fg_color=Theme.COLORS["good"])
            self.summary.configure(text=f"Saved to: {save_path}")
            self.progress_label.configure(text="Status: exported")

        except Exception as e:
            self.badge.configure(text="ERROR", fg_color=Theme.COLORS["bad"])
            self.summary.configure(text=f"Export failed: {e}")
            self.progress_label.configure(text="Status: error")
