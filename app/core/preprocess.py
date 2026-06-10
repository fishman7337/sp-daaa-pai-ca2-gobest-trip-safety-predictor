from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd

from app.core.schema import FIELD_ALIASES, REQUIRED_FIELDS

_TOKENS = {"", "na", "n/a", "null", "nan", "."}
_EPS = 1e-12


def _normalize_key(k: Any) -> str:
    return str(k).strip().lower()


def _apply_aliases(columns: Iterable[str]) -> dict[str, str]:
    cols = list(columns)
    alias_map: dict[str, str] = {}
    for alias, canonical in FIELD_ALIASES.items():
        if canonical not in cols and alias in cols:
            alias_map[alias] = canonical
    return alias_map


def clean_batch_inputs(df: pd.DataFrame, *, fill_missing: bool = True) -> pd.DataFrame:
    df_clean = df.copy()
    df_clean = df_clean.rename(columns={c: _normalize_key(c) for c in df_clean.columns})
    # Drop common artefact columns
    for artefact in ("unnamed: 0", "csv_index"):
        if artefact in df_clean.columns:
            df_clean = df_clean.drop(columns=[artefact])
    alias_map = _apply_aliases(df_clean.columns)
    if alias_map:
        df_clean = df_clean.rename(columns=alias_map)

    for col in REQUIRED_FIELDS:
        if col not in df_clean.columns:
            continue
        raw = df_clean[col]
        if raw.dtype == object:
            lowered = raw.astype(str).str.strip().str.lower()
            raw = raw.mask(lowered.isin(_TOKENS))
        series = pd.to_numeric(raw, errors="coerce")
        series = series.replace([np.inf, -np.inf], np.nan)
        df_clean[col] = series

    _apply_accuracy_bearing_rules(df_clean)

    if fill_missing:
        for col in REQUIRED_FIELDS:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].fillna(0.0).astype(float)
    return df_clean


def preprocess_inputs_dict(values: dict[str, Any]) -> dict[str, float]:
    normalized = {_normalize_key(k): v for k, v in values.items()}
    alias_map = _apply_aliases(normalized.keys())
    if alias_map:
        normalized = {alias_map.get(k, k): v for k, v in normalized.items()}

    out: dict[str, float] = {}
    for k, v in normalized.items():
        if isinstance(v, str):
            s = v.strip().lower()
            if s in _TOKENS:
                out[k] = math.nan
                continue
        try:
            out[k] = float(v)
        except Exception:
            out[k] = math.nan

    _apply_accuracy_bearing_rules(out)

    for k in REQUIRED_FIELDS:
        if k not in out:
            out[k] = 0.0
    for k, v in list(out.items()):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[k] = 0.0
    return out


def add_engineered_features(values: dict[str, float]) -> dict[str, float]:
    out = dict(values)
    ax = float(out.get("acceleration_x", 0.0))
    ay = float(out.get("acceleration_y", 0.0))
    az = float(out.get("acceleration_z", 0.0))
    gx = float(out.get("gyro_x", 0.0))
    gy = float(out.get("gyro_y", 0.0))
    gz = float(out.get("gyro_z", 0.0))

    out["acc_magnitude"] = math.sqrt(ax * ax + ay * ay + az * az)
    out["gyro_magnitude"] = math.sqrt(gx * gx + gy * gy + gz * gz)
    return out


def aggregate_trip_features(
    df: pd.DataFrame,
    id_col: str = "booking_id",
    *,
    fast: bool = True,
) -> pd.DataFrame:
    if id_col not in df.columns:
        return df.copy()

    base_cols = [id_col]
    if "second" in df.columns:
        base_cols.append("second")
    base_cols += [c for c in REQUIRED_FIELDS if c in df.columns]
    # de-duplicate while preserving order
    seen: set[str] = set()
    base_cols = [c for c in base_cols if not (c in seen or seen.add(c))]
    dfc = df[base_cols].copy()
    # Skip sorting in fast mode to avoid O(n log n) cost on big files.
    if not fast and "second" in dfc.columns:
        dfc = dfc.sort_values([id_col, "second"], kind="mergesort")

    for col in REQUIRED_FIELDS:
        if col in dfc.columns:
            dfc[col] = pd.to_numeric(dfc[col], errors="coerce")

    ax = dfc.get("acceleration_x", 0.0)
    ay = dfc.get("acceleration_y", 0.0)
    az = dfc.get("acceleration_z", 0.0)
    gx = dfc.get("gyro_x", 0.0)
    gy = dfc.get("gyro_y", 0.0)
    gz = dfc.get("gyro_z", 0.0)
    dfc["acc_magnitude"] = np.sqrt(ax * ax + ay * ay + az * az)
    dfc["gyro_magnitude"] = np.sqrt(gx * gx + gy * gy + gz * gz)

    g = dfc.groupby(id_col, sort=False)

    agg_spec: dict[str, list[str]] = {}
    for col in ("speed", "acc_magnitude", "gyro_magnitude", "accuracy"):
        if col in dfc.columns:
            agg_spec[col] = ["mean", "std", "min", "max"]
    for col in ("acceleration_x", "acceleration_y", "acceleration_z"):
        if col in dfc.columns:
            agg_spec[col] = ["mean", "std"]

    out = g.agg(agg_spec)
    out.columns = [
        f"{c[0].replace('acceleration', 'acc') if c[0].startswith('acceleration') else c[0]}_{c[1]}"
        for c in out.columns
    ]
    out = out.reset_index()

    if "second" in dfc.columns:
        t_min = g["second"].min().rename("t_min")
        t_max = g["second"].max().rename("t_max")
        n_samples = g["second"].count().rename("n_samples")
        out = out.merge(t_min, on=id_col).merge(t_max, on=id_col).merge(n_samples, on=id_col)
        out["trip_duration_s"] = out["t_max"] - out["t_min"]
        out["sampling_rate_hz"] = out["n_samples"] / out["trip_duration_s"].replace(0, np.nan)
        out = out.drop(columns=["t_min", "t_max"])
    else:
        out["n_samples"] = g.size().to_numpy()
        out["trip_duration_s"] = math.nan
        out["sampling_rate_hz"] = math.nan

    # Percentiles are expensive; keep placeholders in fast mode.
    if "speed" in dfc.columns:
        out["speed_p90"] = math.nan
    if "acc_magnitude" in dfc.columns:
        out["acc_mag_p95"] = math.nan
    if "gyro_magnitude" in dfc.columns:
        out["gyro_mag_p95"] = math.nan

    if "speed" in dfc.columns:
        first_speed = g["speed"].first().rename("start_speed")
        last_speed = g["speed"].last().rename("end_speed")
        out = out.merge(first_speed, on=id_col).merge(last_speed, on=id_col)
    else:
        out["start_speed"] = math.nan
        out["end_speed"] = math.nan

    # Ensure expected columns exist even in fast mode
    for col in (
        "speed_change_rate_med",
        "jerk_med",
        "jerk_p95",
        "turn_delta_std_deg",
        "turn_rate_med_deg_s",
    ):
        if col not in out.columns:
            out[col] = math.nan

    if not fast and "second" in dfc.columns:
        def _speed_change_rate(group: pd.DataFrame) -> float:
            spd = group.get("speed")
            t = group.get("second")
            if spd is None or t is None:
                return math.nan
            spd = spd.to_numpy(dtype=float)
            t = t.to_numpy(dtype=float)
            if spd.size < 2 or t.size < 2:
                return math.nan
            dt = np.diff(t)
            dx = np.diff(spd)
            dt[dt == 0] = np.nan
            scr = np.abs(dx / dt)
            scr = scr[np.isfinite(scr)]
            if scr.size == 0:
                return math.nan
            return float(np.nanmedian(scr))

        def _jerk_stats(group: pd.DataFrame) -> tuple[float, float]:
            t = group.get("second")
            accm = group.get("acc_magnitude")
            if t is None or accm is None:
                return math.nan, math.nan
            t = t.to_numpy(dtype=float)
            accm = accm.to_numpy(dtype=float)
            if t.size < 2 or accm.size < 2:
                return math.nan, math.nan
            dt = np.diff(t)
            dacc = np.diff(accm)
            dt[dt == 0] = np.nan
            jerk = np.abs(dacc / dt)
            jerk = jerk[np.isfinite(jerk)]
            if jerk.size == 0:
                return math.nan, math.nan
            return float(np.nanmedian(jerk)), float(np.percentile(jerk, 95))

        def _turn_stats(group: pd.DataFrame) -> tuple[float, float]:
            t = group.get("second")
            bear = group.get("bearing")
            if t is None or bear is None:
                return math.nan, math.nan
            t = t.to_numpy(dtype=float)
            b = bear.to_numpy(dtype=float)
            if t.size < 2 or b.size < 2:
                return math.nan, math.nan
            b = b[np.isfinite(b)]
            if b.size < 2:
                return math.nan, math.nan
            b_unwrap = np.rad2deg(np.unwrap(np.deg2rad(b)))
            dtheta = np.abs(np.diff(b_unwrap))
            if dtheta.size == 0:
                return math.nan, math.nan
            turn_std = float(np.nanstd(dtheta, ddof=0))
            dt = np.diff(t[: dtheta.size + 1])
            dt[dt == 0] = np.nan
            tr = dtheta / dt
            tr = tr[np.isfinite(tr)]
            turn_rate_med = float(np.nanmedian(np.abs(tr))) if tr.size else math.nan
            return turn_std, turn_rate_med

        speed_change = g.apply(_speed_change_rate).rename("speed_change_rate_med")
        jerk_stats = g.apply(_jerk_stats)
        turn_stats = g.apply(_turn_stats)

        out = out.merge(speed_change, on=id_col)
        out["jerk_med"] = jerk_stats.apply(lambda x: x[0]).to_numpy()
        out["jerk_p95"] = jerk_stats.apply(lambda x: x[1]).to_numpy()
        out["turn_delta_std_deg"] = turn_stats.apply(lambda x: x[0]).to_numpy()
        out["turn_rate_med_deg_s"] = turn_stats.apply(lambda x: x[1]).to_numpy()

    return out


def aggregate_trip_features_streaming(
    csv_path: str,
    *,
    id_col: str = "booking_id",
    chunksize: int = 200_000,
) -> pd.DataFrame:
    def _merge_stats(acc: dict[str, dict[str, float]], row: pd.Series) -> None:
        bid = row[id_col]
        if bid not in acc:
            acc[bid] = row.to_dict()
            return
        cur = acc[bid]
        for k, v in row.items():
            if k == id_col:
                continue
            if k.endswith("_min"):
                cur[k] = v if cur.get(k) is None else min(cur[k], v)
            elif k.endswith("_max"):
                cur[k] = v if cur.get(k) is None else max(cur[k], v)
            else:
                cur[k] = (cur.get(k) or 0.0) + (v or 0.0)

    acc: dict[str, dict[str, float]] = {}
    usecols = None

    for chunk in pd.read_csv(csv_path, chunksize=chunksize):
        chunk = clean_batch_inputs(chunk)
        if id_col not in chunk.columns:
            return aggregate_trip_features(chunk, id_col=id_col, fast=True)

        base_cols = [id_col]
        if "second" in chunk.columns:
            base_cols.append("second")
        base_cols += [c for c in REQUIRED_FIELDS if c in chunk.columns]
        seen: set[str] = set()
        base_cols = [c for c in base_cols if not (c in seen or seen.add(c))]
        if usecols is None:
            usecols = base_cols
        chunk = chunk[usecols]

        ax = chunk.get("acceleration_x", 0.0)
        ay = chunk.get("acceleration_y", 0.0)
        az = chunk.get("acceleration_z", 0.0)
        gx = chunk.get("gyro_x", 0.0)
        gy = chunk.get("gyro_y", 0.0)
        gz = chunk.get("gyro_z", 0.0)
        chunk["acc_magnitude"] = np.sqrt(ax * ax + ay * ay + az * az)
        chunk["gyro_magnitude"] = np.sqrt(gx * gx + gy * gy + gz * gz)

        g = chunk.groupby(id_col, sort=False)

        stats_cols = [c for c in ("speed", "acc_magnitude", "gyro_magnitude", "accuracy",
                                  "acceleration_x", "acceleration_y", "acceleration_z")
                      if c in chunk.columns]
        for c in stats_cols:
            chunk[f"{c}__sq"] = chunk[c] * chunk[c]

        agg_spec: dict[str, list[str]] = {}
        for c in stats_cols:
            agg_spec[c] = ["sum", "min", "max", "count"]
            agg_spec[f"{c}__sq"] = ["sum"]
        if "second" in chunk.columns:
            agg_spec["second"] = ["min", "max", "count"]

        part = g.agg(agg_spec)
        part.columns = [
            f"{c[0].replace('acceleration', 'acc') if c[0].startswith('acceleration') else c[0]}_{c[1]}"
            for c in part.columns
        ]
        part = part.reset_index()

        for _, row in part.iterrows():
            _merge_stats(acc, row)

    rows = []
    for bid, d in acc.items():
        row = {id_col: bid}
        # second
        t_min = d.get("second_min")
        t_max = d.get("second_max")
        n_samples = d.get("second_count", 0.0)
        row["n_samples"] = int(n_samples) if n_samples is not None else 0
        row["trip_duration_s"] = (t_max - t_min) if t_min is not None and t_max is not None else math.nan
        row["sampling_rate_hz"] = (
            row["n_samples"] / row["trip_duration_s"]
            if row.get("trip_duration_s") not in (0, None, math.nan)
            else math.nan
        )

        def _mean_std(prefix: str, stats: dict[str, float] = d) -> tuple[float, float, float, float]:
            s = stats.get(f"{prefix}_sum", 0.0)
            ss = stats.get(f"{prefix}__sq_sum", 0.0)
            cnt = stats.get(f"{prefix}_count", 0.0) or 0.0
            if cnt == 0:
                return math.nan, math.nan, math.nan, math.nan
            mean = s / cnt
            var = max((ss / cnt) - (mean * mean), 0.0)
            return mean, math.sqrt(var), stats.get(f"{prefix}_min", math.nan), stats.get(f"{prefix}_max", math.nan)

        for src, out_name in (
            ("speed", "speed"),
            ("acc_magnitude", "acc_mag"),
            ("gyro_magnitude", "gyro_mag"),
            ("accuracy", "gps_acc"),
            ("acc_x", "acc_x"),
            ("acc_y", "acc_y"),
            ("acc_z", "acc_z"),
        ):
            mean, std, vmin, vmax = _mean_std(src)
            row[f"{out_name}_mean"] = mean
            row[f"{out_name}_std"] = std
            if out_name == "speed":
                row["speed_min"] = vmin
                row["speed_max"] = vmax
            if out_name == "acc_mag":
                row["acc_mag_max"] = vmax

        row["speed_p90"] = math.nan
        row["acc_mag_p95"] = math.nan
        row["gyro_mag_p95"] = math.nan
        row["speed_change_rate_med"] = math.nan
        row["jerk_med"] = math.nan
        row["jerk_p95"] = math.nan
        row["turn_delta_std_deg"] = math.nan
        row["turn_rate_med_deg_s"] = math.nan
        row["start_speed"] = math.nan
        row["end_speed"] = math.nan

        rows.append(row)

    return pd.DataFrame(rows)


def _apply_accuracy_bearing_rules(target: Any) -> None:
    if isinstance(target, pd.DataFrame):
        if "accuracy" in target.columns:
            acc = pd.to_numeric(target["accuracy"], errors="coerce")
            target.loc[acc.notna() & (acc < -_EPS), "accuracy"] = np.nan
        if "bearing" in target.columns:
            brg = pd.to_numeric(target["bearing"], errors="coerce")
            target.loc[brg.notna() & ((brg < (0 - _EPS)) | (brg > (360 + _EPS))), "bearing"] = np.nan
        return

    if "accuracy" in target:
        try:
            acc = float(target["accuracy"])
            if acc < -_EPS:
                target["accuracy"] = math.nan
        except Exception:
            target["accuracy"] = math.nan
    if "bearing" in target:
        try:
            brg = float(target["bearing"])
            if (brg < (0 - _EPS)) or (brg > (360 + _EPS)):
                target["bearing"] = math.nan
        except Exception:
            target["bearing"] = math.nan
