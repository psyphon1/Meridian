# ADR-003 — Code graph + hybrid retrieval over embeddings alone

**Status:** Accepted · **Date:** 2026-09-12

## Context

Agents need repository context to review changes in architectural context. Embedding-similarity retrieval is the common default, but code has structure that pure similarity ignores.

## Decision Drivers

- Reviews must reference real definitions/callers/usages, not lexically similar fragments
- Low-hallucination goal → context must be precise, attributable, and SHA-reproducible
- Cost: token-efficient retrieval beats dumping plausible-but-loose context

## Considered Options

1. **Embeddings only (RAG)** — easy, but confuses "similar text" with "related code"; no call-graph awareness.
2. **Heuristics/grep only** — precise but brittle, no semantic generalization.
3. **Hybrid: Tree-sitter ASTs + SCIP/LSP symbol graph + pgvector + BM25 lexical, with a reranker** — structured grounding plus semantic recall.

## Decision

**Hybrid retrieval grounded in a code graph.** Tree-sitter provides syntax/AST extraction; SCIP/LSP provides definitions/references; git history and repo rules enrich the graph; pgvector (semantic) + Postgres FTS/BM25 (lexical) + reranker combine for final context assembly. Every context item carries a SHA-pinned provenance.

## Consequences

- Positive: agents cite real spans; retrieval is reproducible from a commit SHA; context size bounded by relevance, not luck.
- Negative: indexer is a real subsystem (incremental indexing service, staleness handling) — accepted as a core product differentiator rather than a liability.
