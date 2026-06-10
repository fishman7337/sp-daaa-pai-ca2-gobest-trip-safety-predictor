# GitHub Publishing

Repository name:

```text
sp-daaa-pai-ca2-gobest-trip-safety-predictor
```

Description:

```text
Offline Python desktop app for trip-safety prediction from vehicle sensor data, with batch CSV inference, engineered driving-behavior features, drift checks, and a decision-tree model demo for SP DAAA Practical AI CA2.
```

Suggested topics:

```text
python, machine-learning, scikit-learn, customtkinter, desktop-app,
feature-engineering, classification, decision-tree, trip-safety,
driver-behavior, pytest, singapore-polytechnic, sp-daaa, practical-ai
```

## Local Publish Steps

The GitHub CLI is not installed in the current environment, so create the empty public repo under `fishman7337` first. Then run:

```powershell
git remote add origin https://github.com/fishman7337/sp-daaa-pai-ca2-gobest-trip-safety-predictor.git
git push -u origin main
git tag v0.1.0
git push origin v0.1.0
```

Do not add `_private_submission/` or `dist/` to git.
