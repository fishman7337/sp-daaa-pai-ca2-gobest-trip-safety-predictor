import math

import pandas as pd
import pytest

from app.core.batch import clean_batch_inputs, run_batch
from app.core.data_store import DataStore, FeedbackEntry, PredictionEntry
from app.core.predictor import Prediction, Predictor
from app.core.preprocess import aggregate_trip_features, aggregate_trip_features_streaming
from app.core.validation import REQUIRED_FIELDS, safe_float, validate_numeric_inputs


def _valid_inputs() -> dict[str, str]:
    return {field: "1.5" for field in REQUIRED_FIELDS}


def _set_predictor_shared(pipeline=None, features=None, error=None) -> dict:
    saved = {
        "loaded": Predictor._shared_loaded,
        "pipeline": Predictor._shared_pipeline,
        "features": list(Predictor._shared_features),
        "error": Predictor._shared_error,
        "version": Predictor.MODEL_VERSION,
    }
    Predictor._shared_loaded = True
    Predictor._shared_pipeline = pipeline
    Predictor._shared_features = features or []
    Predictor._shared_error = error
    Predictor.MODEL_VERSION = "Test"
    return saved


def _restore_predictor_shared(saved: dict) -> None:
    Predictor._shared_loaded = saved["loaded"]
    Predictor._shared_pipeline = saved["pipeline"]
    Predictor._shared_features = saved["features"]
    Predictor._shared_error = saved["error"]
    Predictor.MODEL_VERSION = saved["version"]


@pytest.mark.unit
def test_validate_numeric_inputs_ok() -> None:
    res = validate_numeric_inputs(_valid_inputs())
    assert res.ok is True
    assert res.message == "OK"


@pytest.mark.unit
@pytest.mark.parametrize("missing_field", REQUIRED_FIELDS)
def test_validate_numeric_inputs_missing_field(missing_field: str) -> None:
    values = _valid_inputs()
    values.pop(missing_field)
    res = validate_numeric_inputs(values)
    assert res.ok is False
    assert res.message == f"Missing field: {missing_field}"


@pytest.mark.unit
@pytest.mark.parametrize("field", REQUIRED_FIELDS[:3])
def test_validate_numeric_inputs_empty_field(field: str) -> None:
    values = _valid_inputs()
    values[field] = "  "
    res = validate_numeric_inputs(values)
    assert res.ok is False
    assert res.message == f"Field '{field}' cannot be empty"


@pytest.mark.unit
@pytest.mark.parametrize("field", REQUIRED_FIELDS[3:6])
def test_validate_numeric_inputs_non_numeric(field: str) -> None:
    values = _valid_inputs()
    values[field] = "nope"
    res = validate_numeric_inputs(values)
    assert res.ok is False
    assert res.message == f"Field '{field}' must be a number"


@pytest.mark.unit
@pytest.mark.parametrize("field,value", [("speed", "nan"), ("gyro_x", "inf"), ("gyro_y", "-inf")])
def test_validate_numeric_inputs_rejects_non_finite(field: str, value: str) -> None:
    values = _valid_inputs()
    values[field] = value
    res = validate_numeric_inputs(values)
    assert res.ok is False
    assert res.message == f"Field '{field}' must be finite"


@pytest.mark.unit
@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("accuracy", "-0.1", "Field 'accuracy' must be >= 0"),
        ("bearing", "361", "Field 'bearing' must be <= 360"),
        ("second", "-1", "Field 'second' must be >= 0"),
    ],
)
def test_validate_numeric_inputs_rejects_domain_errors(field: str, value: str, expected: str) -> None:
    values = _valid_inputs()
    values[field] = value
    res = validate_numeric_inputs(values)
    assert res.ok is False
    assert res.message == expected


@pytest.mark.unit
@pytest.mark.parametrize("value, expected", [("3.5", 3.5), ("-2", -2.0), ("1e2", 100.0)])
def test_safe_float_parses(value: str, expected: float) -> None:
    assert safe_float(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize("value", ["", "  ", "abc", "nan", "inf"])
def test_safe_float_default_on_error(value: str) -> None:
    assert safe_float(value, default=9.9) == 9.9


@pytest.mark.unit
def test_new_booking_id_format() -> None:
    store = DataStore()
    booking_id = store.new_booking_id()
    assert booking_id.startswith("BK-")
    assert len(booking_id) == 11


@pytest.mark.unit
def test_add_prediction_duplicate_raises() -> None:
    store = DataStore()
    entry = PredictionEntry(booking_id="BK-12345678", predicted_label=1, prob_dangerous=0.9)
    store.add_prediction(entry)
    with pytest.raises(ValueError, match="Booking ID already exists"):
        store.add_prediction(entry)


@pytest.mark.unit
def test_add_feedback_requires_prediction() -> None:
    store = DataStore()
    feedback = FeedbackEntry(booking_id="BK-11111111", felt_safe=True, rating=4, notes="ok")
    with pytest.raises(ValueError, match="Predict first"):
        store.add_feedback(feedback)


@pytest.mark.unit
def test_add_feedback_duplicate_raises() -> None:
    store = DataStore()
    pred = PredictionEntry(booking_id="BK-22222222", predicted_label=0, prob_dangerous=0.1)
    store.add_prediction(pred)
    feedback = FeedbackEntry(booking_id=pred.booking_id, felt_safe=True, rating=5, notes="good")
    store.add_feedback(feedback)
    with pytest.raises(ValueError, match="Feedback already submitted"):
        store.add_feedback(feedback)


@pytest.mark.unit
def test_subscribe_called_on_add_prediction() -> None:
    store = DataStore()
    hits = []

    def _cb() -> None:
        hits.append("pred")

    store.subscribe(_cb)
    store.add_prediction(PredictionEntry(booking_id="BK-33333333", predicted_label=1, prob_dangerous=0.8))
    assert hits == ["pred"]


@pytest.mark.unit
def test_subscribe_called_on_add_feedback() -> None:
    store = DataStore()
    hits = []

    def _cb() -> None:
        hits.append("fb")

    store.subscribe(_cb)
    pred = PredictionEntry(booking_id="BK-44444444", predicted_label=0, prob_dangerous=0.2)
    store.add_prediction(pred)
    store.add_feedback(FeedbackEntry(booking_id=pred.booking_id, felt_safe=True, rating=4, notes="fine"))
    assert hits == ["fb", "fb"]


@pytest.mark.unit
def test_subscribe_returns_unsubscribe() -> None:
    store = DataStore()
    hits = []

    unsubscribe = store.subscribe(lambda: hits.append("hit"))
    unsubscribe()
    store.add_prediction(PredictionEntry(booking_id="BK-10101010", predicted_label=0, prob_dangerous=0.2))
    assert hits == []


@pytest.mark.unit
def test_export_rows_matches_prediction_feedback() -> None:
    store = DataStore()
    pred = PredictionEntry(booking_id="BK-55555555", predicted_label=1, prob_dangerous=0.7)
    store.add_prediction(pred)
    store.add_feedback(FeedbackEntry(booking_id=pred.booking_id, felt_safe=False, rating=2, notes="rough"))
    rows = store.export_rows()
    assert rows == [
        {
            "booking_id": pred.booking_id,
            "predicted_label": "1",
            "actual_label": "1",
            "rating": "2",
            "match": "yes",
        }
    ]


@pytest.mark.unit
def test_stats_no_feedback() -> None:
    store = DataStore()
    store.add_prediction(PredictionEntry(booking_id="BK-66666666", predicted_label=0, prob_dangerous=0.1))
    stats = store.stats()
    assert stats["total"] == 0
    assert stats["total_predictions"] == 1
    assert stats["feedback_rate"] == 0.0
    assert stats["safe_ratio"] == 0.0
    assert stats["avg_rating"] == 0.0
    assert stats["match_rate"] == 0.0


@pytest.mark.unit
def test_stats_with_feedback() -> None:
    store = DataStore()
    pred_safe = PredictionEntry(booking_id="BK-77777777", predicted_label=0, prob_dangerous=0.2)
    pred_risk = PredictionEntry(booking_id="BK-88888888", predicted_label=1, prob_dangerous=0.8)
    store.add_prediction(pred_safe)
    store.add_prediction(pred_risk)
    store.add_feedback(FeedbackEntry(booking_id=pred_safe.booking_id, felt_safe=True, rating=4, notes="ok"))
    store.add_feedback(FeedbackEntry(booking_id=pred_risk.booking_id, felt_safe=False, rating=1, notes="bad"))
    stats = store.stats()
    assert stats["total"] == 2
    assert stats["total_predictions"] == 2
    assert stats["feedback_rate"] == 1.0
    assert stats["safe_ratio"] == 0.5
    assert stats["avg_rating"] == 2.5
    assert stats["match_rate"] == 1.0


@pytest.mark.integration
def test_run_batch_missing_columns_raises(tmp_path) -> None:
    df = pd.DataFrame({"speed": [1.0], "acceleration_x": [0.1]})
    csv_path = tmp_path / "input.csv"
    df.to_csv(csv_path, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        run_batch(Predictor(), str(csv_path), str(tmp_path / "out.csv"))


@pytest.mark.integration
def test_run_batch_outputs_columns(tmp_path) -> None:
    class DummyPredictor:
        def predict_one(self, x):
            return Prediction(label=0, prob_dangerous=0.12, message="ok")

    df = pd.DataFrame([{field: 1.0 for field in REQUIRED_FIELDS}])
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    res, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), return_df=True)
    assert res.rows == 1
    assert res.dangerous_count == 0
    assert "booking_id" in out_df.columns
    assert "prob_dangerous" in out_df.columns
    assert "pred_label" in out_df.columns
    assert "prediction_source" in out_df.columns


@pytest.mark.unit
def test_clean_batch_inputs_coerces_invalid_values() -> None:
    df = pd.DataFrame(
        [
            {
                "speed": " 3.5 ",
                "acceleration_x": "abc",
                "acceleration_y": "",
                "acceleration_z": None,
                "gyro_x": "1e2",
                "gyro_y": float("inf"),
                "gyro_z": "-2",
                "accuracy": "-1",
                "bearing": "400",
                "second": "5",
            }
        ]
    )
    cleaned = clean_batch_inputs(df)
    assert math.isclose(cleaned.loc[0, "speed"], 3.5)
    assert cleaned.loc[0, "acceleration_x"] == 0.0
    assert cleaned.loc[0, "acceleration_y"] == 0.0
    assert cleaned.loc[0, "acceleration_z"] == 0.0
    assert math.isclose(cleaned.loc[0, "gyro_x"], 100.0)
    assert cleaned.loc[0, "gyro_y"] == 0.0
    assert math.isclose(cleaned.loc[0, "gyro_z"], -2.0)
    assert cleaned.loc[0, "accuracy"] == 0.0
    assert cleaned.loc[0, "bearing"] == 0.0
    assert math.isclose(cleaned.loc[0, "second"], 5.0)


@pytest.mark.integration
def test_run_batch_accepts_case_insensitive_columns(tmp_path) -> None:
    class DummyPredictor:
        def predict_one(self, x):
            return Prediction(label=0, prob_dangerous=0.12, message="ok")

    df = pd.DataFrame(
        [
            {
                "Speed": "1",
                "ACCELERATION_X": "2",
                "acceleration_Y": "3",
                "Acceleration_Z": "4",
                "Gyro_X": "5",
                "GYRO_y": "6",
                "gyro_Z": "7",
                "Accuracy": "0.9",
                "Bearing": "180",
                "Second": "10",
            }
        ]
    )
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    res, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), return_df=True)
    assert res.rows == 1
    assert "prob_dangerous" in out_df.columns
    assert math.isclose(out_df.loc[0, "speed"], 1.0)


@pytest.mark.integration
def test_run_batch_accepts_bookingid_header(tmp_path) -> None:
    class DummyPredictor:
        def predict_one(self, x):
            return Prediction(label=0, prob_dangerous=0.12, message="ok")

    df = pd.DataFrame(
        [
            {
                "bookingID": "B1",
                "second": 0,
                "Speed": 10,
                "Accuracy": 1,
                "Bearing": 0,
                "acceleration_x": 1,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
            },
            {
                "bookingID": "B1",
                "second": 10,
                "Speed": 20,
                "Accuracy": 1,
                "Bearing": 10,
                "acceleration_x": 2,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
            },
        ]
    )
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    res, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), return_df=True)
    assert res.rows == 1
    assert out_df.loc[0, "booking_id"] == "B1"


@pytest.mark.unit
def test_clean_batch_inputs_accepts_accuracy_bearing_aliases() -> None:
    df = pd.DataFrame(
        [
            {
                "speed": "2",
                "acceleration_x": "1",
                "acceleration_y": "1",
                "acceleration_z": "1",
                "gyro_x": "1",
                "gyro_y": "1",
                "gyro_z": "1",
                "accuracy_m": "0.25",
                "bearing_deg": "180",
                "second": "3",
            }
        ]
    )
    cleaned = clean_batch_inputs(df)
    assert math.isclose(cleaned.loc[0, "accuracy"], 0.25)
    assert math.isclose(cleaned.loc[0, "bearing"], 180.0)


@pytest.mark.integration
def test_run_batch_uses_cleaned_inputs(tmp_path) -> None:
    seen = {}

    class DummyPredictor:
        def predict_one(self, x):
            seen.update(x)
            return Prediction(label=0, prob_dangerous=0.12, message="ok")

    df = pd.DataFrame(
        [
            {
                "speed": " 7.0 ",
                "acceleration_x": "bad",
                "acceleration_y": "1.2",
                "acceleration_z": "",
                "gyro_x": None,
                "gyro_y": "2",
                "gyro_z": "nan",
                "accuracy": "0.5",
                "bearing": float("inf"),
                "second": "3",
            }
        ]
    )
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    _, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), return_df=True)
    assert math.isclose(seen["speed"], 7.0)
    assert seen["acceleration_x"] == 0.0
    assert math.isclose(seen["acceleration_y"], 1.2)
    assert seen["acceleration_z"] == 0.0
    assert seen["gyro_x"] == 0.0
    assert math.isclose(seen["gyro_y"], 2.0)
    assert seen["gyro_z"] == 0.0
    assert math.isclose(seen["accuracy"], 0.5)
    assert seen["bearing"] == 0.0
    assert math.isclose(seen["second"], 3.0)
    assert math.isclose(out_df.loc[0, "speed"], 7.0)
    assert out_df.loc[0, "bearing"] == 0.0


@pytest.mark.unit
def test_aggregate_trip_features_basic() -> None:
    df = pd.DataFrame(
        [
            {
                "booking_id": "BK-1",
                "second": 0,
                "speed": 10,
                "acceleration_x": 1,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 0,
            },
            {
                "booking_id": "BK-1",
                "second": 10,
                "speed": 20,
                "acceleration_x": 2,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 10,
            },
        ]
    )
    agg = aggregate_trip_features(df, id_col="booking_id")
    assert len(agg) == 1
    assert agg.loc[0, "booking_id"] == "BK-1"
    assert math.isclose(agg.loc[0, "speed_mean"], 15.0)
    assert math.isclose(agg.loc[0, "trip_duration_s"], 10.0)


@pytest.mark.integration
def test_run_batch_aggregates_by_booking_id(tmp_path) -> None:
    class DummyPredictor:
        def predict_one(self, x):
            return Prediction(label=1, prob_dangerous=0.9, message="ok")

    df = pd.DataFrame(
        [
            {
                "booking_id": "BK-1",
                "second": 0,
                "speed": 10,
                "acceleration_x": 1,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 0,
            },
            {
                "booking_id": "BK-1",
                "second": 10,
                "speed": 20,
                "acceleration_x": 2,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 10,
            },
        ]
    )
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    res, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), return_df=True)
    assert res.rows == 1
    assert out_df.loc[0, "booking_id"] == "BK-1"
    assert math.isclose(out_df.loc[0, "avg_speed"], 15.0)


@pytest.mark.unit
def test_aggregate_trip_features_streaming_matches_non_stream(tmp_path) -> None:
    df = pd.DataFrame(
        [
            {
                "booking_id": "BK-1",
                "second": 0,
                "speed": 10,
                "acceleration_x": 1,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 0,
            },
            {
                "booking_id": "BK-1",
                "second": 10,
                "speed": 20,
                "acceleration_x": 2,
                "acceleration_y": 0,
                "acceleration_z": 0,
                "gyro_x": 0,
                "gyro_y": 0,
                "gyro_z": 0,
                "accuracy": 1,
                "bearing": 10,
            },
        ]
    )
    csv_path = tmp_path / "input.csv"
    df.to_csv(csv_path, index=False)

    stream = aggregate_trip_features_streaming(str(csv_path), id_col="booking_id", chunksize=1)
    direct = aggregate_trip_features(df, id_col="booking_id", fast=True)
    assert math.isclose(stream.loc[0, "speed_mean"], direct.loc[0, "speed_mean"])
    assert math.isclose(stream.loc[0, "trip_duration_s"], direct.loc[0, "trip_duration_s"])


@pytest.mark.integration
def test_run_batch_with_store_includes_booking_id(tmp_path) -> None:
    class DummyPredictor:
        def predict_one(self, x):
            return Prediction(label=1, prob_dangerous=0.88, message="risk")

    store = DataStore()
    df = pd.DataFrame([{field: 2.0 for field in REQUIRED_FIELDS}])
    csv_path = tmp_path / "input.csv"
    out_path = tmp_path / "out.csv"
    df.to_csv(csv_path, index=False)

    res, out_df = run_batch(DummyPredictor(), str(csv_path), str(out_path), store=store, return_df=True)
    assert res.dangerous_count == 1
    assert "booking_id" in out_df.columns
    assert store.last_booking_id in set(out_df["booking_id"])


@pytest.mark.unit
def test_predictor_fallback_when_model_unavailable() -> None:
    saved = _set_predictor_shared(pipeline=None, features=[], error="missing")
    try:
        predictor = Predictor()
        pred = predictor.predict_one({"speed": 1.0})
        assert pred.message.endswith("Model unavailable.)")
        assert pred.source == "heuristic_fallback"
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.unit
def test_predictor_fallback_prob_increases_with_risk() -> None:
    saved = _set_predictor_shared(pipeline=None, features=[], error="missing")
    try:
        predictor = Predictor()
        low = predictor.predict_one({"speed": 1.0})
        high = predictor.predict_one({"speed": 80.0, "acceleration_x": 3.0, "gyro_z": 2.0})
        assert high.prob_dangerous > low.prob_dangerous
        assert high.source == "heuristic_fallback"
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.unit
def test_predictor_predicts_with_dummy_pipeline() -> None:
    class DummyPipeline:
        def __init__(self) -> None:
            self.classes_ = [0, 1]

        def predict_proba(self, df):
            return [[0.2, 0.8]]

    saved = _set_predictor_shared(pipeline=DummyPipeline(), features=["speed"])
    try:
        predictor = Predictor()
        pred = predictor.predict_one({"speed": 4.0})
        assert pred.label == 1
        assert math.isclose(pred.prob_dangerous, 0.8)
        assert pred.message == "Model prediction completed."
        assert pred.source == "model"
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.unit
def test_predictor_uses_engineered_features() -> None:
    class DummyPipeline:
        def __init__(self) -> None:
            self.classes_ = [0, 1]

        def predict_proba(self, df):
            assert "acc_magnitude" in df.columns
            val = float(df.loc[0, "acc_magnitude"])
            return [[0.2, 0.8]] if val >= 3.0 else [[0.9, 0.1]]

    saved = _set_predictor_shared(pipeline=DummyPipeline(), features=["acc_magnitude"])
    try:
        predictor = Predictor()
        pred = predictor.predict_one(
            {"acceleration_x": 1.0, "acceleration_y": 2.0, "acceleration_z": 2.0}
        )
        assert pred.label == 1
        assert math.isclose(pred.prob_dangerous, 0.8)
        assert pred.message == "Model prediction completed."
        assert pred.source == "model"
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.unit
def test_predictor_uses_prefixed_trip_features() -> None:
    class DummyPipeline:
        def __init__(self) -> None:
            self.classes_ = [0, 1]

        def predict_proba(self, df):
            assert "num__fe_n_samples" in df.columns
            assert "num__rating" in df.columns
            return [[0.3, 0.7]]

    saved = _set_predictor_shared(
        pipeline=DummyPipeline(),
        features=["num__fe_n_samples", "num__rating"],
    )
    try:
        predictor = Predictor()
        pred = predictor.predict_one({"fe_n_samples": 12})
        assert pred.label == 1
        assert math.isclose(pred.prob_dangerous, 0.7)
        assert pred.source == "model"
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.smoke
def test_checked_in_model_artifact_loads() -> None:
    saved = _set_predictor_shared()
    try:
        Predictor._shared_loaded = False
        Predictor._shared_pipeline = None
        Predictor._shared_features = []
        Predictor._shared_error = None
        Predictor.MODEL_VERSION = "Dummy v0"
        predictor = Predictor()
        assert Predictor.model_status() == "Decision Tree v1 pipeline"
        assert predictor.feature_names
    finally:
        _restore_predictor_shared(saved)


@pytest.mark.unit
def test_batch_preview_mix_does_not_duplicate_rows() -> None:
    pytest.importorskip("customtkinter")
    from app.ui.pages.batch_page import BatchPage

    df = pd.DataFrame(
        {
            "booking_id": ["B1", "B2", "B3", "B4"],
            "pred_label": [0, 1, 0, 1],
            "prob_dangerous": [0.1, 0.9, 0.2, 0.8],
        }
    )
    preview = BatchPage._load_preview_mix(None, df, nrows=4)
    assert len(preview) == 4
    assert preview["booking_id"].is_unique
