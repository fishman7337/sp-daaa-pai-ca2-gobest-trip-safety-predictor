$ErrorActionPreference = "Stop"

python -m ruff check .
python -m pytest -q
python -m pip check
python -c "from app.core.predictor import Predictor; p=Predictor(); print(f'{Predictor.model_status()} | features={len(p.feature_names)}')"
