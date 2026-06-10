# Security Policy

## Supported Versions

This student project is maintained as a public portfolio and learning artifact. Security fixes are accepted for the current `main` branch.

## Reporting Issues

Please open a private report with the maintainer if available, or create a GitHub issue that avoids sharing exploit details, secrets, or private data publicly.

## Data And Artifact Safety

- Do not commit credentials, database URLs, SSH keys, raw datasets, or school declaration files.
- Do not load untrusted `.joblib`, `.pkl`, or pickle-based artifacts. These formats can execute code during loading.
- Treat prediction outputs and feedback exports as potentially sensitive local data.
- This app is not approved for real safety-critical decision-making.
