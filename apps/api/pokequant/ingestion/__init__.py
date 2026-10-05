"""Ingestion: raw observations -> consolidated daily snapshots.

Two entry points: a synthetic backfill (offline bootstrap) and a live pass over
configured providers. Both record a `provider_runs` row for observability.
"""
