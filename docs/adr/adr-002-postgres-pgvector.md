# ADR-002 — PostgreSQL + pgvector first; Qdrant only on metric trigger

**Status:** Accepted · **Date:** 2026-09-12

## Context

Repository intelligence needs semantic search over code symbols and history. The design doc's principle "PostgreSQL = truth" pushes against adding a second stateful system.

## Decision Drivers

- Minimize operational surface and consistency risk in V1 (one transactional system of record)
- Expected V1 scale: symbol embeddings per repo are well within pgvector + HNSW capability
- A dedicated vector DB only pays off at a scale we can measure, not guess

## Considered Options

1. **pgvector in Postgres** — one source of truth, transactional with the symbol tables, sufficient ANN performance at V1 scale.
2. **Qdrant from day one** — best-in-class vector filtering/performance, but a second stateful system to deploy, back up, and keep consistent with Postgres.
3. **Embeddings in Redis** — wrong durability/consistency profile for the system of record.

## Decision

**PostgreSQL + pgvector is the V1 system of record, including embeddings.** Introduce Qdrant **only** when a measured metric trigger fires (sustained retrieval p95 above SLO, or dataset size per tenant beyond pgvector's efficient envelope) — not speculatively.

## Consequences

- Positive: transactional consistency between findings, symbols, and embeddings; one backup/retention/deletion story (cascading deletion is one system, not two).
- Negative: retrieval ceiling may arrive sooner than with a dedicated engine — mitigated by the explicit metric trigger and by keeping the retrieval package interface vector-store-agnostic (swappable without touching agents).
