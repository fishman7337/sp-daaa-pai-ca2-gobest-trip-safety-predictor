import pandas as pd

from app.core.drift import DriftMonitor
from app.core.validation import REQUIRED_FIELDS


def test_drift_monitor_detects_shift() -> None:
    monitor = DriftMonitor(REQUIRED_FIELDS, reference_size=5, window_size=5, z_threshold=2.0)
    baseline = {f: 0.0 for f in REQUIRED_FIELDS}

    report = None
    for _ in range(5):
        report = monitor.update(baseline)

    assert report is not None
    assert report.ref_ready is True
    assert report.window_ready is False

    for _ in range(4):
        report = monitor.update(baseline)
        assert report.window_ready is False

    report = monitor.update(baseline)
    assert report.window_ready is True
    assert report.drifted is False

    shifted = {f: 10.0 for f in REQUIRED_FIELDS}
    for _ in range(5):
        report = monitor.update(shifted)

    assert report is not None
    assert report.window_ready is True
    assert report.drifted is True


def test_drift_analyze_dataframe() -> None:
    monitor = DriftMonitor(REQUIRED_FIELDS, reference_size=5, window_size=5, z_threshold=2.0)

    baseline_rows = [{f: 0.0 for f in REQUIRED_FIELDS} for _ in range(5)]
    shifted_rows = [{f: 10.0 for f in REQUIRED_FIELDS} for _ in range(5)]
    df = pd.DataFrame(baseline_rows + shifted_rows)

    report = monitor.analyze_dataframe(df)
    assert report.ref_ready is True
    assert report.window_ready is True
    assert report.drifted is True
