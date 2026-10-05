# ADR-0007 — Explainability as a first-class, mandatory output

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering, Quant Research, Product
- **Supersedes / Superseded by:** —

## Context

PokéQuant makes recommendations about money. Users (and interviewers) will not — and should not — trust a black-box number. The brief is explicit: *never output black-box predictions.* Explanations also serve engineering (debugging, leakage detection) and product (trust, education). The risk is the opposite failure mode: an LLM that fabricates plausible-but-false reasons or numbers.

## Decision

Explainability is a **mandatory, first-class output**, not an optional add-on:

1. Every forecast persists **SHAP attributions** (local) tied to its exact model + feature versions; global SHAP validates feature importance and detects leakage.
2. The Investment Score and Risk assessment are **decomposable by construction** and stored with their components.
3. Natural-language summaries are generated **facts-first**: SHAP/score/risk facts → deterministic template → optional LLM rephrase that is **grounded and validated** (no number/entity may appear that isn't in the fact set; failing that, we use the template). Numbers shown to users always come from computation.

If a prediction cannot be explained, it is not surfaced as a signal.

## Alternatives considered

- **Post-hoc "explanations" written freely by an LLM.** Fluent but unfaithful and prone to hallucinated figures — actively misleading for financial signals. Rejected.
- **Only global feature importance (no per-prediction).** Cheap, but can't answer "why *this* one?"; insufficient for a product page. Rejected as the sole mechanism.
- **Inherently interpretable models only (linear).** Maximally transparent but leaves accuracy on the table vs. GBM/TFT. Rejected in favor of accurate models + SHAP, which recovers interpretability without capping accuracy.

## Consequences

- Positive: trustworthy, auditable, reproducible explanations; a strong differentiator and interview talking point; a built-in debugging/leakage-detection tool.
- Negative / cost: SHAP compute per prediction (mitigated by TreeExplainer speed + caching); the guardrail/validation layer adds engineering; explanations are of the *model*, not ground-truth causality (stated honestly to users).
- Follow-ups: implement the pipeline and storage in [08](../08-explainable-ai.md); add SHAP-vs-score consistency checks to admin; keep LLM strictly in a rephrasing role.
