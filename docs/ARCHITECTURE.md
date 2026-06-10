# Architecture

The app is a small offline desktop system with a clear split between prediction logic and CustomTkinter UI pages.

## Runtime Flow

1. `app/main.py` starts the `App` shell and creates one shared `DataStore`.
2. UI pages call core services for validation, prediction, batch processing, drift checks, and feedback storage.
3. `Predictor` loads `decision_tree_pipeline.joblib` once and shares the loaded pipeline across instances.
4. Batch CSVs with booking IDs are cleaned, grouped, engineered into trip-level features, predicted, and exported.
5. Feedback and admin pages read from the in-memory store for local demo workflows.

## Main Modules

- `app/core/schema.py`: shared input fields, aliases, labels, limits, and prediction labels.
- `app/core/validation.py`: strict real-time input validation.
- `app/core/preprocess.py`: batch/dataframe cleaning and legacy aggregation helpers.
- `app/core/feature_engineering.py`: canonical trip-level feature engineering for the decision-tree model.
- `app/core/predictor.py`: model loading, model input construction, and heuristic fallback.
- `app/core/batch.py`: CSV batch inference and export.
- `app/core/data_store.py`: in-memory predictions, feedback, stats, and listener notifications.
- `app/ui/pages/`: desktop screens for real-time, batch, feedback, admin, and about views.

## Important Design Notes

- The bundled model expects engineered trip-level features. Single raw sensor records use a labeled heuristic fallback.
- The UI never requires internet access.
- The store is intentionally in memory; persistence can be added with SQLite if needed.
- Batch worker threads do file/model work only. UI and store updates are marshalled back to the Tkinter thread.
