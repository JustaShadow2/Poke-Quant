"""Batch pipelines wiring repositories + ML together (features, training, forecasting).

These are the DB-backed equivalents of the pure functions in `ml/` and `features/`.
In production they run under an orchestrator (Prefect, Phase 2); in Phase 1 they
are invoked via the CLI.
"""
