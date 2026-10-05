"""Repository pattern: the only place that speaks SQLAlchemy.

Services depend on the Protocols in `ports.py`, not on these concrete classes,
so the domain/service layer stays persistence-agnostic and unit-testable with
in-memory fakes (docs/13-engineering-standards.md - Repository pattern + DI).
"""
