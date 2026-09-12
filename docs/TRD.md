# Meridian — Technical Requirements Document (TRD)

**Owner:** Chinmay Duse (psyphon1) · **Version:** 2.1
Full detail in [`design/Meridian_TRD.md`](design/Meridian_TRD.md). This is the working technical contract for V1.

---

## 1. Technology Requirements

| Layer | Technology | Requirement |
|---|---|---|
| Frontend | Next.js + TypeScript (strict) | Dashboard, onboarding, live status, cost meter |
| Identity | GitHub OAuth App | Session only; separate from GitHub App |
| Repo access | GitHub App | Installation-scoped access, webhooks, review publish |
| API | FastAPI | Async webhooks + dashboard API, OpenAPI, versioned |
| Workflow | LangGraph | Checkpointed after every node; resumable by stateless workers |
| Queue | Redis Streams | Consumer groups, per-tenant priority lanes |
| Parsing / code intel | Tree-sitter; SCIP/LSP | AST extraction; definitions/references |
| DB | PostgreSQL (+ pgvector V1) | System of record; partitioned by tenant/repo |
| Retrieval | pgvector + PG FTS/BM25 + reranker | Hybrid semantic + lexical |
| LLM gateway | LiteLLM | Per-request BYOK injection |
| Analysis | Semgrep; CodeQL | Deterministic + deep data-flow evidence |
| Execution | Firecracker/gVisor path, pre-warmed pool | Per-tenant isolated, deny-all egress |
| Secrets | AWS/GCP KMS or Vault | Envelope-encrypted user keys |
| Observability | OpenTelemetry + Langfuse | Redacted before export |
| Infra | Docker, Kubernetes, Terraform, GitHub Actions | Reproducible deploy |

## 2. Performance / SLA Requirements

| Metric | Target |
|---|---|
| Webhook → queued | < 10 sec (bounded by GitHub's webhook response window) |
| Standard review | p50 < 3 min, p95 < 8 min |
| Critical/deep review | p95 < 15 min |
| Webhook availability | 99.9% |
| Signup → first repo connected | < 5 min |

### 2.1 SLO Frame (Google SRE golden signals)

The table above is measured as SLIs and protected by SLOs, per golden-signal practice — **alert on symptoms, reserve cause-oriented alerts for debugging**:

| Signal | SLI | SLO |
|---|---|---|
| Latency | Webhook-ack latency (99th percentile, never averages) | p99 < 10 s |
| Latency | Time-to-first-useful-review distribution | p50 < 3 min, p95 < 8 min |
| Traffic | Webhooks/sec, jobs/min by tier, tokens/min by tenant | Capacity planning input |
| Errors | Signature-failure rate, pipeline FAILED rate, drop rate | Zero silent drops; FAILED < 0.5% |
| Saturation | Queue depth per lane, sandbox pool utilization, DB connection saturation | Page before saturation → meltdown (N+0 is "nearly full") |

Error budget: 0.1% webhook unavailability (~43 min/month). Budget burn > 2x triggers review-freeze-until-fixed for reliability work.

## 3. Security & Reliability Requirements

- Signature-verified webhooks; idempotent inserts (`repository_id + pr_number + head_sha` unique, advisory lock).
- Keys: envelope encryption, in-memory-only decryption, never logged; rotation from V1.
- Deny-all sandbox egress; command allowlists; CPU/mem/wall-clock limits.
- Bounded retries; checkpointed workflows; explicit `PARTIAL_REVIEW`; no silent drops.
- Redacted traces; append-only hash-chained audit log; cascading verified deletion (SLA ≤ 30 days).

## 4. Quality Gates (V1 minimum)

No blocking comment without evidence_ref · SHA-pinned citations on every finding · dedupe findings · review reproducible from commit SHA · repo rules affect review · security-sensitive PRs get deeper checks · tenant-isolated sandbox · visible failures · observable latency · keys never in logs/traces/exports · verifiable deletion.

## 5. Implementation Order

```
P1  GitHub App + FastAPI + PostgreSQL + Redis
P2  LangGraph workflow + basic LLM review
P3  Tree-sitter + SCIP/LSP + repo indexing
P4  Hybrid retrieval + historical context
P5  Specialized agents + risk routing
P6  Semgrep + CodeQL + sandbox verification
P7  Evidence gate + citations + escalation
P8  Observability + audit + cost controls
P9  Production hardening + benchmark
```

## 6. Technical Definition of Done

GitHub events signature-verified · idempotent · incremental repo intelligence · symbols/references available · hybrid retrieval works · conditional agent routing · evidence-gated high-impact findings · SHA-pinned citations · isolated sandbox · encrypted keys never logged · workflow survives worker failure · explicit partial failure · audit events recorded · cost/latency measurable · regression benchmark passes.
