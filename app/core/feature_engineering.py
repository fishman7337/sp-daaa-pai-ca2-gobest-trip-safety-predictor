from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FEConfig:
    """Configuration for behaviour-level feature engineering."""
    eps: float = 1e-9

    stop_speed: float = 0.5
    move_speed: float = 2.0
    min_speed_turn: float = 3.0

    hard_brake_dv: float = 2.5
    rapid_accel_dv: float = 2.5
    sharp_turn_rate: float = 15.0
    bearing_jump: float = 90.0

    high_speed: float = 15.0
    robust_z_spike: float = 6.0

    w_brake: float = 1.0
    w_accel: float = 1.0
    w_turn: float = 1.0
    w_high_speed: float = 1.5
    w_jerk: float = 1.0


def wrap_angle_delta_deg(curr: np.ndarray, prev: np.ndarray) -> np.ndarray:
    delta = (curr - prev) % 360.0
    return np.where(delta > 180.0, delta - 360.0, delta)


def robust_spike_count(x: np.ndarray, z_thresh: float, eps: float) -> int:
    s = pd.Series(x).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        return 0
    med = s.median()
    mad = (s - med).abs().median()
    z = 0.6745 * (s - med) / (mad + eps)
    return int((z.abs() >= z_thresh).sum())


def longest_true_streak(mask: np.ndarray) -> int:
    if mask.size == 0:
        return 0
    max_run = 0
    run = 0
    for v in mask:
        if v:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return int(max_run)


def compute_trip_features(
    df_trip: pd.DataFrame,
    cfg: FEConfig,
    *,
    id_col: str = "booking_id",
    rating_col: str = "rating",
    default_rating: float = 3.0,
) -> dict[str, Any]:
    trip_id = df_trip[id_col].iloc[0]

    sec = pd.to_numeric(df_trip.get("second"), errors="coerce").to_numpy(dtype=float)
    spd = pd.to_numeric(df_trip.get("speed"), errors="coerce").to_numpy(dtype=float)
    brg = pd.to_numeric(df_trip.get("bearing"), errors="coerce").to_numpy(dtype=float)

    ax = pd.to_numeric(df_trip.get("acceleration_x"), errors="coerce").to_numpy(dtype=float)
    ay = pd.to_numeric(df_trip.get("acceleration_y"), errors="coerce").to_numpy(dtype=float)
    az = pd.to_numeric(df_trip.get("acceleration_z"), errors="coerce").to_numpy(dtype=float)

    gz = pd.to_numeric(df_trip.get("gyro_z"), errors="coerce").to_numpy(dtype=float)
    accy = pd.to_numeric(df_trip.get("accuracy"), errors="coerce").to_numpy(dtype=float)

    rating = default_rating
    if rating_col in df_trip.columns:
        try:
            rating = float(pd.to_numeric(df_trip[rating_col], errors="coerce").dropna().iloc[0])
        except Exception:
            rating = default_rating

    valid_t = np.isfinite(sec)
    sec, spd, brg, ax, ay, az, gz, accy = (
        sec[valid_t],
        spd[valid_t],
        brg[valid_t],
        ax[valid_t],
        ay[valid_t],
        az[valid_t],
        gz[valid_t],
        accy[valid_t],
    )

    n = sec.size
    if n < 2:
        return {
            id_col: trip_id,
            "fe_n_samples": int(n),
            "fe_trip_duration_s": 0.0,
            "fe_hard_brake_rate_pm": 0.0,
            "fe_rapid_accel_rate_pm": 0.0,
            "fe_sharp_turn_rate_pm": 0.0,
            "fe_high_speed_risk_rate_pm": 0.0,
            "fe_bearing_jump_rate_pm": 0.0,
            "fe_stop_segments": 0,
            "fe_restarts": 0,
            "fe_stop_fraction": 0.0,
            "fe_longest_aggressive_streak": 0,
            "fe_jerk_energy_norm": 0.0,
            "fe_jerk_spike_count": 0,
            "fe_dvdt_spike_count": 0,
            "fe_turn_rate_spike_count": 0,
            "fe_hard_brake_weighted": 0.0,
            "fe_rapid_accel_weighted": 0.0,
            "fe_aggression_index": 0.0,
            "rating": float(rating),
        }

    t_min = float(np.nanmin(sec))
    t_max = float(np.nanmax(sec))
    duration = max(cfg.eps, t_max - t_min)
    minutes = duration / 60.0

    dt = np.diff(sec)
    dt = np.where(~np.isfinite(dt) | (dt <= 0), 1.0, dt)

    dv = np.diff(spd)
    dv_dt = dv / dt

    brg_prev = brg[:-1]
    brg_curr = brg[1:]
    dbrg = wrap_angle_delta_deg(brg_curr, brg_prev)
    turn_rate = dbrg / dt

    acc_mag = np.sqrt(ax * ax + ay * ay + az * az)
    dacc = np.diff(acc_mag)
    jerk = dacc / dt

    gps_conf = 1.0 / (accy + 1.0)

    spd_mid = spd[1:]
    hard_brake = np.isfinite(dv_dt) & (dv_dt < -cfg.hard_brake_dv)
    rapid_accel = np.isfinite(dv_dt) & (dv_dt > cfg.rapid_accel_dv)

    sharp_turn = (
        np.isfinite(turn_rate)
        & (np.abs(turn_rate) > cfg.sharp_turn_rate)
        & np.isfinite(spd_mid)
        & (spd_mid > cfg.min_speed_turn)
    )

    bearing_jump = (
        np.isfinite(dbrg)
        & (np.abs(dbrg) > cfg.bearing_jump)
        & np.isfinite(spd_mid)
        & (spd_mid > cfg.min_speed_turn)
    )

    high_speed_turn = sharp_turn & (spd_mid > cfg.high_speed)
    high_speed_brake = hard_brake & (spd_mid > cfg.high_speed)

    aggressive = hard_brake | rapid_accel | sharp_turn

    gps_w = gps_conf[1:]
    hard_brake_w = float(np.nansum(gps_w * hard_brake))
    rapid_accel_w = float(np.nansum(gps_w * rapid_accel))

    stopped = np.isfinite(spd) & (spd < cfg.stop_speed)
    moving = np.isfinite(spd) & (spd > cfg.move_speed)

    stop_edges = np.diff(stopped.astype(int), prepend=0)
    stop_segments = int((stop_edges == 1).sum())

    restart_edges = (stopped[:-1] & moving[1:]).astype(int)
    restarts = int(restart_edges.sum())

    stop_fraction = float(np.nanmean(stopped.astype(float)))

    jerk_energy = float(np.nansum(jerk * jerk * dt))
    jerk_energy_norm = jerk_energy / duration

    jerk_spike_count = robust_spike_count(jerk, z_thresh=cfg.robust_z_spike, eps=cfg.eps)
    dv_dt_spike_count = robust_spike_count(dv_dt, z_thresh=cfg.robust_z_spike, eps=cfg.eps)
    turn_rate_spike_count = robust_spike_count(turn_rate, z_thresh=cfg.robust_z_spike, eps=cfg.eps)

    hard_brake_rate_pm = float(hard_brake.sum()) / minutes
    rapid_accel_rate_pm = float(rapid_accel.sum()) / minutes
    sharp_turn_rate_pm = float(sharp_turn.sum()) / minutes
    bearing_jump_rate_pm = float(bearing_jump.sum()) / minutes
    high_speed_risk_rate_pm = float((high_speed_turn | high_speed_brake).sum()) / minutes

    longest_aggressive = longest_true_streak(aggressive)

    aggression_index = (
        cfg.w_brake * hard_brake_rate_pm
        + cfg.w_accel * rapid_accel_rate_pm
        + cfg.w_turn * sharp_turn_rate_pm
        + cfg.w_high_speed * high_speed_risk_rate_pm
        + cfg.w_jerk * (jerk_spike_count / minutes)
    )

    return {
        id_col: trip_id,
        "fe_n_samples": int(n),
        "fe_trip_duration_s": float(duration),
        "fe_hard_brake_rate_pm": hard_brake_rate_pm,
        "fe_rapid_accel_rate_pm": rapid_accel_rate_pm,
        "fe_sharp_turn_rate_pm": sharp_turn_rate_pm,
        "fe_high_speed_risk_rate_pm": high_speed_risk_rate_pm,
        "fe_bearing_jump_rate_pm": bearing_jump_rate_pm,
        "fe_stop_segments": stop_segments,
        "fe_restarts": restarts,
        "fe_stop_fraction": stop_fraction,
        "fe_longest_aggressive_streak": longest_aggressive,
        "fe_jerk_energy_norm": jerk_energy_norm,
        "fe_jerk_spike_count": int(jerk_spike_count),
        "fe_dvdt_spike_count": int(dv_dt_spike_count),
        "fe_turn_rate_spike_count": int(turn_rate_spike_count),
        "fe_hard_brake_weighted": hard_brake_w / minutes,
        "fe_rapid_accel_weighted": rapid_accel_w / minutes,
        "fe_aggression_index": float(aggression_index),
        "rating": float(rating),
    }


def compute_trip_features_frame(
    df: pd.DataFrame,
    *,
    id_col: str = "booking_id",
    cfg: FEConfig | None = None,
    default_rating: float = 3.0,
) -> pd.DataFrame:
    if id_col not in df.columns:
        return df.copy()
    cfg = cfg or FEConfig()
    rows = []
    for _, g in df.groupby(id_col, sort=False):
        rows.append(
            compute_trip_features(
                g,
                cfg,
                id_col=id_col,
                default_rating=default_rating,
            )
        )
    return pd.DataFrame(rows)
