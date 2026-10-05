# ADR-0003 — PostgreSQL + TimescaleDB as the primary datastore

- **Status:** Accepted
- **Date:** 2026-06-30
- **Deciders:** Engineering
- **Supersedes / Superseded by:** —

## Context

PokéQuant has three data shapes: (1) **relational/transactional** (users, portfolios, transactions, instruments, model metadata) needing integrity and joins; (2) **time-series** (price observations, daily snapshots, features) needing efficient range scans, downsampling, and retention; and (3) **vectors** (product embeddings for similarity). Operating three specialized systems (e.g., Postgres + InfluxDB + a vector DB) multiplies operational surface, cross-store consistency problems, and cost.

## Decision

We will use **PostgreSQL** as the single system of record, extended with **TimescaleDB** (hypertables, continuous aggregates, compression, retention) for time-series and **pgvector** for embeddings/ANN search. One backup story, one connection pool, one query language, transactional consistency across all three shapes.

## Alternatives considered

- **Postgres + InfluxDB/QuestDB (separate TSDB).** Best-in-class TSDB features, but a second datastore to run/monitor/back up, and cross-store joins (price + instrument metadata) become app-side. Timescale gives ~90% of the TSDB benefit inside Postgres. Rejected initially; documented as a scale-out option if time-series volume explodes.
- **Postgres + dedicated vector DB (Pinecone/Milvus/Qdrant).** Superior ANN at massive scale, but our catalog is thousands–tens-of-thousands of instruments; pgvector's HNSW indexes are more than sufficient and keep vectors next to their metadata. Rejected initially.
- **A single NoSQL/document store.** Poor fit for the relational integrity that portfolio/transaction correctness demands. Rejected.

## Consequences

- Positive: one datastore to operate; transactional consistency (a snapshot write and its derived rows commit together); joins across metadata + series + vectors; managed Postgres+Timescale offerings exist for both deployment tracks.
- Negative / cost: Postgres is not a horizontally-sharded TSDB; extreme time-series scale would eventually need partitioning strategy work or extraction to a dedicated TSDB.
- Follow-ups: define hypertable chunk intervals, continuous aggregates (daily/weekly), compression policy for old chunks, and retention for raw observations in [03 — Database Design](../03-database-design.md).
