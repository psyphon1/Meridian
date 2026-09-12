# Meridian — Compliance & Audit

**Per v2 spec §15 — compliance/audit is a first-class server-side dependency, not an afterthought.**

> **AI agents:** [`AGENTS.md`](../AGENTS.md) is your entry point — audit logging, retention, and redaction rules here are non-negotiable in any code you write.

---

## 1. Append-Only Audit Log

Separate store from operational Postgres (prevents accidental mutation). Every row is **hash-chained** (each row includes the hash of the prior row) so tampering is detectable.

**Logged events:** login · key add/rotate/delete · GitHub App install/uninstall · repo connect/disconnect · review start/status-transition/finish · every finding published · data export · deletion request · config change.

Row shape: `id, user_id, event_type, target_resource, payload_redacted, prev_hash, row_hash, created_at`.

## 2. Data Retention & Deletion

- Retention configurable per user (repo content, model traces, embeddings); default **90 days**, adjustable within policy limits.
- Deletion must **actually cascade**: uninstall or account deletion purges repo content, symbol index, embeddings, review memory, and observability traces — not a soft-delete flag.
- Deletion request verifiably cascades within SLA (e.g., 30 days) — a V1 quality gate.

## 3. Redaction

No raw code, diffs, or keys leave the tenant boundary into shared observability tooling — hash or truncate before export to OpenTelemetry/Langfuse.

## 4. Baseline

SOC2-shaped controls assumed: access logging, retention policy, deletion workflow, encryption at rest and in transit. Formal certification not claimed. If GDPR/HIPAA/etc. becomes required, storage/retention design must be revisited (per design doc).
