"""Calibrated synthetic historical data (see docs/adr/0005-synthetic-historical-backfill.md).

Real historical *sealed* price series are scarce, so we bootstrap development and
cold-start models with a calibrated generative model. Synthetic data is always
flagged (`is_synthetic`) and must never silently drive user-facing advice.
"""
