# Model Card

## Model

- Artifact: `decision_tree_pipeline.joblib`
- Family: scikit-learn decision-tree pipeline
- Task: binary trip-safety classification
- Labels: `0 = SAFE`, `1 = DANGEROUS`

## Intended Use

This model is included for an educational desktop demo for Practical AI CA2 (ST1508). It can demonstrate local model loading, batch inference, feature engineering, and UI integration.

It must not be used for real-world safety, employment, insurance, enforcement, dispatch, or driver evaluation decisions.

## Inputs

The checked-in model expects trip-level engineered features such as:

- `fe_n_samples`
- `fe_trip_duration_s`
- hard-brake, rapid-acceleration, sharp-turn, high-speed-risk, bearing-jump rates
- stop, restart, jerk, spike, and aggression-index features
- `rating`

Raw batch CSVs with booking IDs are converted into these features before prediction. Single real-time sensor records do not contain enough trip history, so the app explicitly uses a heuristic fallback for that screen when needed.

## Outputs

The app exports:

- `prob_dangerous`: probability-like model or fallback score in the range `0..1`
- `pred_label`: `0` for safe, `1` for dangerous
- `prediction_source`: `model` or `heuristic_fallback`

## Limitations

- Training data is not included in this public repository.
- Public docs do not claim production-grade accuracy or fairness.
- The fallback heuristic is only a UI demo path and is not a trained model.
- Sensor data quality, device mounting, GPS accuracy, and class imbalance can affect behaviour.
- Joblib artifacts should only be loaded from trusted sources.

## Maintenance

When replacing the model artifact:

1. Update `Predictor.MODEL_FILENAME` or keep the same artifact name.
2. Confirm `Predictor._extract_feature_names` detects the expected feature list.
3. Update this model card with training data, metrics, limitations, and intended use.
4. Run `python -m pytest -q`.
