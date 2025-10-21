# VCSelector POC

This proof of concept implements the core workflow from the VCSelector design: ingest startup profiles, score them, derive investment strategies, and surface health alerts for monitoring teams.

## Layout
- `data/startups_fixture.json` – sample dataset covering multiple sectors and stages.
- `src/models.py` – domain definitions for startup profiles, scoring factors, strategies, and alerts.
- `src/ingestion.py` – loader that converts JSON fixtures into domain objects.
- `src/services/scoring.py` – heuristic scoring engine with explainable factor contributions.
- `src/services/strategy.py` – maps scores to strategy recommendations based on fund configuration.
- `src/services/monitoring.py` – generates health signals (runway, burn, sentiment).
- `src/pipeline.py` – coordinates scoring, strategy, and monitoring into a single run.
- `poc.py` – executable runner emitting JSON summary of the evaluation.

## Running

```bash
cd VCSelector
python poc.py --verbose
```

Parameters:
- `--data-file` path to startup dataset.
- `--fund-name` fund configuration label.
- `--check-size` base check size (millions USD).
- `--ownership-floor` minimum desired ownership percentage.
- `--verbose` toggles debug logs.

The script prints ranked scores with factor contributions, strategy recommendations, and any health alerts. Extend the services to integrate with real feature stores, MLOps pipelines, or alerting systems.
