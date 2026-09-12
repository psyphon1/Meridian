# Meridian — Autonomous AI PR Reviewer
# System Design Document (SDD)

**Owner:** Chinmay Duse (psyphon1) · **Version:** 2.1
**Structure follows arc42/C4-informed SDD practice:** context → building blocks → key design decisions → data design → failure handling. Full detail in [`design/Meridian_SDD.md`](design/Meridian_SDD.md).

---

## 1. System Purpose & Context

Meridian is an autonomous first-pass GitHub PR reviewer. It replaces the manual senior-initiated review loop with an event-driven pipeline; humans remain final merge authority.

## 2. Design Goals

Repository-aware review · autonomous first pass · evidence-backed findings · low hallucination · risk-adaptive compute · token-efficient BYOK · deterministic verification · human escalation for uncertainty · strong tenant isolation · full auditability · reproducibility from a commit SHA.

## 3. Architectural Principles (separation of concerns)

```
LLM = reasoning          Tree-sitter = syntax/AST        SCIP/LSP = structure
Retrieval = context      Semgrep/CodeQL = deterministic  Sandbox = execution proof
PostgreSQL = truth       LangGraph = orchestration       GitHub App = SCM boundary
Human = final authority
```

## 4. Building Blocks (pipeline)

```
GitHub PR
 → Webhook Gateway (signature verify, idempotency: repo+pr+head_sha unique + advisory lock)
 → Redis Streams (consumer groups, per-tenant priority lanes)
 → LangGraph Orchestrator (checkpointed after every node)
 → Intent Analysis → Change Localization → Risk Classification
 → Repository Context Retrieval (cached; Tree-sitter + SCIP/LSP + git history + rules)
 → Conditional Multi-Agent Review (Correctness/Security/Performance/Architecture/Reliability/Test)
 → Evidence Planner → Semgrep/CodeQL/Sandbox/Tests → Evidence Verifier
 → Adjudicator (schema-enforced evidence gate) → Publish / Suppress / Escalate
```

Agents produce **hypotheses**, never final comments; no agent both invents and confirms its own claim.

## 5. Evidence Gate (core mechanism, schema-enforced)

- `IF severity ∈ (BLOCKING, HIGH)`: `evidence_ref` must be non-null, of type `tool_run | test_execution | sha_pinned_code_span`, and the adjudicator must re-derive the claim from the artifact — else downgrade to INFO or suppress.
- Every published comment carries a SHA-pinned permalink: `github.com/{owner}/{repo}/blob/{head_sha}/{path}#L{start}-L{end}`.

## 6. Data Design

Core entities (PostgreSQL, partitioned by tenant/repo): `users`, `api_keys` (envelope-encrypted), `installations`, `repositories`, `pull_requests`, `commits`, `files`, `code_symbols` (+ pgvector embeddings), `review_runs`, `findings`, `evidence`, `tool_runs`, `rules`, `review_memory`, `audit_events` (append-only, hash-chained, separate store).

## 7. Trust Boundary (prompt-injection defense)

```
System Policy > Review Policy > Repository Rules > Repository Content > PR/User Text
```

Repo content never enters system/developer roles; structured JSON outputs; tool allowlists; no unrestricted shell.

## 8. Isolation (tenant = user, BYOK)

KMS envelope-encrypted keys, decrypted only in worker memory at call time and zeroized after. Per-tenant execution namespace; per-job ephemeral sandbox from pre-warmed pool; deny-all egress except allowlisted registries.

## 9. Failure Handling

| Failure | Mitigation |
|---|---|
| Hallucination | Evidence gate + confidence filtering |
| Duplicate webhook | DB unique constraint + advisory lock |
| Tool unavailable | Graceful degradation → `PARTIAL_REVIEW` |
| Sandbox exhaustion | Visible queue state, per-tenant cap |
| GitHub rate limit | Token bucket, backoff, circuit breaker → delayed queue |
| Runaway spend | Hard per-tenant daily ceiling |

Full state machine: `RECEIVED → VALIDATED → QUEUED → CONTEXT_BUILDING → ANALYZING → VERIFYING → ADJUDICATING → PUBLISHING/ESCALATED → COMPLETED` (failures: `FAILED`, `PARTIAL_REVIEW`, `QUEUED_NO_KEY`).

## 10. Queue Design (Redis Streams — detailed semantics)

The gateway `XADD`s a canonical job message; workers consume via **named consumer groups** (`XREADGROUP`), one group per pipeline stage. Production rules derived from Redis Streams semantics:

- **At-least-once delivery.** A message is only removed from the Pending Entries List (PEL) by `XACK` *after* the pipeline state transition is durably committed (LangGraph checkpoint). Crash-before-ack ⇒ redelivery ⇒ every consumer must be idempotent (guarded by the webhook unique constraint + delivery ID).
- **Crashed-consumer recovery.** A janitor loop runs `XAUTOCLAIM` (min-idle-time configured per stage) to steal pending entries from dead consumers and re-enqueue them with an attempt counter; after N attempts the job goes to a dead-letter stream for human inspection — no silent drops.
- **Per-tenant priority lanes.** Separate streams (or priority fields + fair scheduling) so one tenant's deep review cannot starve another's; per-tenant in-flight caps enforced at claim time.
- **Stream hygiene.** Bounded streams via `XTRIM` (MAXLEN-based) after checkpoint handoff; job payloads reference DB rows rather than embedding large diffs.

## 11. GitHub Integration Contract

| Concern | Design |
|---|---|
| Auth | App private key (JWT) → installation token per install; token cache keyed by installation ID, regenerate on 401, honor `Retry-After` for secondary limits |
| Ingest | HMAC-SHA256 signature check, `X-GitHub-Delivery` idempotency, event+action filter, 2xx within 10 s (see ARCHITECTURE.md) |
| Publish | Review via PR reviews API; comments cite SHA-pinned permalinks; no line-number guessing — resolve via the blob at `head_sha` |
| Lifecycle | React to `installation` (created/deleted/new_permissions_accepted) and `installation_repositories` (added/removed) to sync install state |
| Deletion | Uninstall triggers cascading data purge (COMPLIANCE.md), recorded in the audit log |
