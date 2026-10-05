# ADR-0001 — Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

PokéQuant is a design-first project with many non-obvious, consequential choices (datastore, service topology, extensibility model, data-collection legality, ML interval strategy). Without a durable record of *why* each choice was made, future contributors (and the author, months later) will re-open settled debates, and reviewers cannot evaluate the reasoning.

## Decision

We will document every architecturally significant decision as an **Architecture Decision Record** stored in `docs/adr/`, using the Nygard format (Context / Decision / Alternatives / Consequences). ADRs are numbered sequentially and are immutable once Accepted; changes are made by adding a superseding ADR.

A decision is "architecturally significant" if it is expensive to reverse, affects multiple modules, constrains future options, or is likely to be questioned.

## Alternatives considered

- **No formal record (rely on commit messages / PR descriptions).** Cheapest, but reasoning is scattered and lost; alternatives-rejected are never captured. Rejected.
- **A single `DECISIONS.md` log.** Simple, but grows unwieldy, has no per-decision status lifecycle, and merges poorly. Rejected in favor of one file per decision.
- **A wiki / external tool (Notion, Confluence).** Decouples decisions from the code that implements them and rots. Rejected: ADRs live in-repo, versioned with the code.

## Consequences

- Positive: decisions are discoverable, reviewable, and versioned alongside the code; onboarding and interview walk-throughs become trivial.
- Negative / cost: minor authoring overhead per significant decision.
- Follow-ups: seed ADRs 0002–0010 alongside the initial design; add a CI check (later) that a PR touching architecture references or adds an ADR.
