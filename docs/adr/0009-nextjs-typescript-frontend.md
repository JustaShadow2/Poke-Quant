# ADR-0009 — Next.js + TypeScript for the web frontend

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

The product is data-dense and chart-heavy (a "terminal" for collectibles): fast dashboards, deep product pages that should be shareable/SEO-friendly, real-time-ish updates, and financial-grade charts. We want strong typing against the API, a large component ecosystem, and a stack recruiters recognize.

## Decision

We will build the web app with **Next.js 15 (App Router) + TypeScript**, **Tailwind CSS** + **shadcn/ui** for the design system, **TanStack Query** for server-state, and **TradingView `lightweight-charts`** for price charts (with **visx/Recharts** for bespoke analytics). The API client's types are **generated from the backend's OpenAPI schema**, so the front/back contract is compiler-checked.

## Alternatives considered

- **SvelteKit.** Excellent DX and performance, smaller ecosystem and talent pool; fewer finance-charting integrations. Rejected (ecosystem/familiarity).
- **Remix / plain React SPA.** Remix is strong; a plain SPA loses SSR/SEO for public product pages and needs more routing/data plumbing. Rejected in favor of Next's SSR/ISR + ecosystem.
- **Server-rendered templates (Jinja/HTMX).** Simplest, but insufficient for rich interactive charts, portfolio UIs, and the assistant. Rejected.

## Consequences

- Positive: SSR/ISR for shareable, fast product pages; typed client eliminates a class of integration bugs; rich charting; recognizable, hireable stack.
- Negative / cost: a JS toolchain alongside Python (managed via `pnpm` in the monorepo); SSR adds some deployment complexity.
- Follow-ups: define the design system, pages, and wireframes in [10 — UX Design](../10-ux-design.md); generate and publish the typed client from OpenAPI in CI.
