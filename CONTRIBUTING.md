# Contributing

Thanks for improving the Gobest Cab Trip Safety Predictor.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Checks

Run these before opening a pull request:

```powershell
python -m ruff check .
python -m pytest -q
```

## Contribution Guidelines

- Keep private submission files, raw datasets, credentials, and generated outputs out of git.
- Add or update tests when changing prediction, preprocessing, validation, or batch behaviour.
- Keep UI wording truthful about whether a prediction came from the model or heuristic fallback.
- Use synthetic/anonymized examples only.
- Update `docs/MODEL_CARD.md` when model behaviour, artifacts, or limitations change.

## Commit Style

Use short imperative commit messages, for example:

```text
Add model smoke test
Fix batch output booking IDs
Document fallback prediction mode
```
