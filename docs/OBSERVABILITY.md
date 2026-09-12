# Meridian — Observability

**Framework: Google SRE golden signals (latency, traffic, errors, saturation) over OpenTelemetry; Langfuse for LLM-specific tracing.** Alert on **symptoms**, not causes — page a human only for urgent, user-visible problems; everything else is a dashboard/ticket.

---

## 1. Golden Signals → Meridian Metrics

| Signal | Metrics | Where |
|---|---|---|
| **Latency** | Webhook-ack duration (p50/p95/p99 — always percentiles, never averages); per-pipeline-stage duration; time-to-first-useful-review; LLM call duration per tier | OTel spans |
| **Traffic** | Webhooks/sec (by event), jobs/min by risk tier, tokens/min & cost/min per tenant | OTel metrics |
| **Errors** | Signature-verification failures, enqueue failures, pipeline FAILED/PARTIAL_REVIEW rates, GitHub API error classes (401/403/429), sandbox failures | OTel + logs |
| **Saturation** | Redis stream depth per lane + PEL age, sandbox pool utilization, DB connection pool usage, worker CPU/mem | OTel metrics |

## 2. Alerting Policy

| Class | Channel | Rule of thumb |
|---|---|---|
| **Page** (urgent, symptom) | Pager | Webhook ingest down/failing SLO; silent-drop detected; audit-log write failure; queue depth trending to meltdown |
| **Ticket** (needs attention, not urgent) | Issue queue | Error-budget burn > threshold, PEL age growth, sustained sandbox saturation |
| **Dashboard only** | Grafana/dashboards | Subcritical subcomponent slowness, token-spend trends |

Email alerts are explicitly avoided (noise-prone). Any page with a rote, algorithmic response is a red flag → automate it or demote it.

## 3. Tracing

- OpenTelemetry spans across the pipeline: `webhook.verify → enqueue → stage:<name> (per LangGraph node) → evidence.run:<tool> → adjudicate → publish`. Every span carries `tenant_id`, `repo`, `pr`, `run_id`, `risk_tier` (never code content, never keys).
- **Langfuse** for LLM-specific observability: prompt/response latencies, token counts, model, per-agent; exported **only after redaction** (hash/truncate any code fragments — COMPLIANCE.md §3).
- Trace → audit-log correlation via `run_id`; the hash-chained audit log is the tamper-evident system of record, dashboards are advisory.

## 4. Logging

- Structured JSON logs, consistent timestamping (UTC), actor/IP/hostname recorded for security-relevant events (auth events, config changes, permission changes, object reads/writes) — mirrored into the audit log.
- Hard redaction at the logging boundary: repository content, diffs, prompts, key material → never. Automated secret-scan runs against log sinks in CI and staging.
- `X-GitHub-Delivery` ID logged on every webhook touch for end-to-end delivery tracing (also the redelivery/idempotency key).

## 5. Dashboards (minimum set)

1. **Tenant experience** — time-to-first-review percentiles, review success rate, escalation rate, spend/PR.
2. **Pipeline health** — stage durations, queue depth per lane, PEL age, dead-letter count (target: zero, alert on any).
3. **GitHub integration** — delivery latency, signature failures, API rate-limit headroom, token cache hit rate.
4. **Sandbox** — pool size, provisioning latency, egress-denied events (security signal), OOM/timeout counts.
