# Meridian — Architecture

**Full document:** [`Meridian_Architecture.md`](design/Meridian_Architecture.md) · **Master design:** [`Meridian_Design_Doc_Final.html`](design/Meridian_Design_Doc_Final.html)

## Summary

Meridian separates: reasoning (LLM) + code intelligence (Tree-sitter/SCIP-LSP) + retrieval + deterministic verification (Semgrep/CodeQL/sandbox) + execution isolation + policy + human escalation. **The LLM is not the source of truth** — it is one reasoning component inside an evidence-driven system.

## System Context (C4-1)

Developer → GitHub PR → webhook → **Meridian** (FastAPI gateway → queue → LangGraph workflow → repo intel / risk engine / model gateway → agents → evidence engine → adjudication) → GitHub review / human escalation. Supporting: PostgreSQL+pgvector, KMS/Vault, OpenTelemetry+Langfuse, Terraform/K8s.

## Key Decisions

| ADR | Decision |
|---|---|
| ADR-001 | GitHub App (installation-scoped) over personal tokens |
| ADR-002 | PostgreSQL + pgvector first; Qdrant only on metric trigger |
| ADR-003 | Code graph + hybrid retrieval over embeddings alone |
| ADR-004 | Evidence gate for high-severity findings (schema-enforced) |
| ADR-005 | Human escalation for high-impact decisions |

## Architectural North Star

Meridian = senior engineer's investigation process + static-analysis platform + repository intelligence engine + secure execution environment + GitHub-native workflow. It builds context → reasons → gathers evidence → verifies → decides → publishes → escalates.

## Webhook Ingestion Contract (production constraints, per GitHub docs)

GitHub enforces a **10-second response window** on webhook deliveries; slower handlers are killed and the delivery marked failed. The ingest contract is therefore:

1. **Verify → enqueue → ack.** Validate the `X-Hub-Signature-256` HMAC against the webhook secret (high-entropy, stored in the secret manager, rotatable), then persist the delivery and return `2xx` within 10 s. All real work happens in the worker via Redis Streams — never inline.
2. **Idempotency & replay defense.** Use `X-GitHub-Delivery` as the delivery identity (it is stable across manual redeliveries); combine with the `repository_id + pr_number + head_sha` unique constraint and advisory lock so a replay or redelivery is a no-op.
3. **Event/action filter at the edge.** Check `X-GitHub-Event` **and** the payload's top-level `action` before enqueueing; subscribe to the minimum event set (installation, installation_repositories, pull_request) to cut latency and cost.
4. **Network posture.** HTTPS with SSL verification enabled; optionally allowlist GitHub's webhook IPs (`GET /meta`), refreshed periodically since GitHub changes them.
5. **Missed-delivery recovery.** Track the last processed delivery cursor; on worker outage recovery, redeliver missed events via the API rather than assuming none were lost.
6. **Permission changes.** New App permissions require user re-approval; the App must stay backwards-compatible and listen for `installation` `new_permissions_accepted`.

### GitHub App credential lifecycle (per GitHub best practices)

- Minimum permissions only; treat any token/secret as revocable — the breach plan (rotate private key, revoke installation tokens via `DELETE /installation/token`, rotate webhook secret) is documented and drillable.
- Installation tokens are short-lived; cache them (keyed by installation ID) and regenerate on 401, staying under both primary rate limits and secondary/abuse limits (honor `Retry-After`).
- Security-relevant logging: authentication events, config changes, permission changes, object reads/writes — consistently timestamped, with actor/IP/hostname recorded (feeds the audit log).
