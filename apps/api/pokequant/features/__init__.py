"""Point-in-time feature engineering (docs/04-feature-engineering.md).

Every feature is computed using only information available at the as-of date
(trailing windows, no centering, no look-ahead) to prevent leakage.
"""
