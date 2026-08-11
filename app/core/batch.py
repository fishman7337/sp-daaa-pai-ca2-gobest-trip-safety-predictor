"""Run batch trip safety predictions from CSV inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pandas as pd

from app.core.data_store import DataStore, PredictionEntry
from app.core.feature_engineering import compute_trip_features_frame
from app.core.predictor import Predictor
from app.core.preprocess import clean_batch_inputs
from app.core.schema import REQUIRED_FIELDS


@dataclass
class BatchResult:
    """Summarize the output of a batch prediction run.

    Attributes:
        output_path: Path of the generated prediction CSV.
        rows: Number of predicted trips written to the CSV.
        dangerous_count: Number of trips classified as dangerous.
    """

    output_path: str
    rows: int
    dangerous_count: int


__all__ = ["run_batch", "BatchResult", "clean_batch_inputs"]


def _new_booking_id() -> str:
    return f"BK-{uuid.uuid4().hex[:8].upper()}"


def run_batch(
    predictor: Predictor,
    csv_path: str,
    output_path: str,
    store: DataStore | None = None,
    *,
    return_df: bool = True,
) -> tuple[BatchResult, pd.DataFrame | None]:
    """Predict trip safety for every trip represented in a CSV file.

    Args:
        predictor: Predictor used to classify each trip.
        csv_path: Path to the source CSV.
        output_path: Path where prediction results are written.
        store: Optional in-memory store that receives each prediction.
        return_df: Whether to return the generated result frame.

    Returns:
        A batch summary and, when requested, the generated result frame.

    Raises:
        ValueError: If the CSV lacks the fields required for prediction.
    """
    # Read header only to decide fast path
    header_df = pd.read_csv(csv_path, nrows=0)
    header_cols = [str(c).strip().lower() for c in header_df.columns]
    if "bookingid" in header_cols and "booking_id" not in header_cols:
        header_cols.append("booking_id")
    has_booking_id = "booking_id" in header_cols
    has_fe_cols = any(c.startswith("fe_") for c in header_cols) or any(c.startswith("num__fe_") for c in header_cols)
    has_required = all(c in header_cols for c in REQUIRED_FIELDS)

    df = None
    if not has_booking_id or has_fe_cols:
        df = pd.read_csv(csv_path)
        df = df.rename(columns={c: str(c).strip().lower() for c in df.columns})
        if "accuracy" not in df.columns and "accuracy_m" in df.columns:
            df = df.rename(columns={"accuracy_m": "accuracy"})
        if "bearing" not in df.columns and "bearing_deg" in df.columns:
            df = df.rename(columns={"bearing_deg": "bearing"})

    if not has_booking_id:
        missing = [c for c in REQUIRED_FIELDS if c not in df.columns]
        if missing and not has_fe_cols:
            raise ValueError(f"CSV missing required columns: {missing}")
        if not has_fe_cols:
            df = clean_batch_inputs(df)

    probs = []
    labels = []
    sources = []
    output_booking_ids = []

    if has_booking_id:
        if has_fe_cols:
            df_feat = df.copy()
        elif has_required:
            df_raw = pd.read_csv(csv_path)
            df_raw = df_raw.rename(columns={c: str(c).strip().lower() for c in df_raw.columns})
            if "accuracy" not in df_raw.columns and "accuracy_m" in df_raw.columns:
                df_raw = df_raw.rename(columns={"accuracy_m": "accuracy"})
            if "bearing" not in df_raw.columns and "bearing_deg" in df_raw.columns:
                df_raw = df_raw.rename(columns={"bearing_deg": "bearing"})
            df_raw = clean_batch_inputs(df_raw, fill_missing=False)
            df_feat = compute_trip_features_frame(df_raw, id_col="booking_id")

            g = df_raw.groupby("booking_id", sort=False)
            counts = g.size().rename("n_samples_raw")
            mean_cols = [c for c in REQUIRED_FIELDS if c in df_raw.columns]
            means = g[mean_cols].mean(numeric_only=True).add_prefix("avg_")
            df_feat = df_feat.merge(counts, on="booking_id", how="left")
            df_feat = df_feat.merge(means, on="booking_id", how="left")
        else:
            raise ValueError("CSV missing required sensor columns to compute trip features.")
    else:
        df_feat = df.copy()

    for _, row in df_feat.iterrows():
        x = {k: row[k] for k in row.index}
        pred = predictor.predict_one(x)
        probs.append(pred.prob_dangerous)
        labels.append(pred.label)
        sources.append(pred.source)
        src_booking_id = row.get("booking_id")
        if src_booking_id is None or pd.isna(src_booking_id) or str(src_booking_id).strip() == "":
            booking_id = _new_booking_id()
        else:
            booking_id = str(src_booking_id)
        if store is not None:
            try:
                store.add_prediction(
                    PredictionEntry(
                        booking_id=booking_id,
                        predicted_label=pred.label,
                        prob_dangerous=pred.prob_dangerous,
                    )
                )
            except ValueError:
                booking_id = store.new_booking_id()
                store.add_prediction(
                    PredictionEntry(
                        booking_id=booking_id,
                        predicted_label=pred.label,
                        prob_dangerous=pred.prob_dangerous,
                    )
                )
        output_booking_ids.append(booking_id)

    df_out = df_feat.copy()
    if "booking_id" in df_out.columns:
        if store is not None:
            df_out["app_booking_id"] = output_booking_ids
    else:
        df_out["booking_id"] = output_booking_ids
    df_out["prob_dangerous"] = probs
    df_out["pred_label"] = labels  # 0 safe, 1 dangerous
    df_out["prediction_source"] = sources
    df_out = df_out.dropna(axis=1, how="all")
    df_out.to_csv(output_path, index=False)

    res = BatchResult(
        output_path=output_path,
        rows=len(df_out),
        dangerous_count=int(sum(labels)),
    )
    if not return_df:
        return res, None
    return res, df_out
