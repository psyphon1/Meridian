# Meridian — Security Policy

**Structure follows SANS information-security policy practice and OWASP ASVS verification categories.** Baseline: SOC2-shaped controls (per v2 spec §15); revisit if a formal framework (GDPR Art. 17, HIPAA) becomes required.

> **AI agents:** [`AGENTS.md`](../AGENTS.md) is your entry point — every security rule here (trust hierarchy, secrets handling, sandbox posture) applies to agent-written code without exception.

---

## 1. Boundary Model

| Boundary | Controls |
|---|---|
| **GitHub** | Minimum-permission GitHub App, webhook signature verification (HMAC), short-lived installation tokens, HTTPS-only, idempotency |
| **Tenant** | tenant = user (no RBAC V1); tenant-scoped data, isolated per-tenant execution namespace, no cross-tenant runtime sharing, even transiently |
| **AI** | Repo/PR content is untrusted input; trust hierarchy `System Policy > Review Policy > Repo Rules > Repo Content > PR Text`; structured JSON outputs; tool allowlists + argument validation; no unrestricted shell |

## 2. Secrets & Key Management

- BYOK keys submitted over TLS → envelope-encrypted with KMS (per-user DEK wrapped by KEK in AWS/GCP KMS or Vault). Only ciphertext persisted.
- Decrypted **only** inside the isolated worker process at LLM-call time; held in memory; zeroized after. Never in logs, traces, prompts, comments, or on disk.
- Key rotation and multi-provider keys supported from V1.
- No repository content or user keys in application logs, ever.

## 3. Sandbox Execution Security

Deny-all network egress by default (explicit registry allowlist only) · command allowlists · CPU/memory/wall-clock/process limits · filesystem isolation · ephemeral per-job runtime from a tenant-scoped pre-warmed pool · Firecracker/gVisor direction for stronger isolation.

## 4. Standards Alignment

- **OWASP ASVS v5.0.0** — application security verification standard, used both as a checklist and as procurement-grade requirements. Requirement IDs are cited as `v5.0.0-<chapter>.<section>.<requirement>` (e.g. `v5.0.0-1.2.5` injection prevention). Meridian targets **ASVS Level 2** (sensitive-data app, protection against skilled attackers) for all auth, key-management, and webhook flows; Level 1 is the floor everywhere else.
- **OWASP Top 10 for LLM Applications** — mapped below with concrete mitigations:

| # | Risk | Meridian control |
|---|---|---|
| LLM01 | Prompt Injection | Trust hierarchy (§1); repo/PR text only in untrusted roles; structured JSON output schemas; instruction-detection heuristics; repo rules separated from repo content |
| LLM02 | Insecure Output Handling | No LLM output executed or interpolated into shell/templates; schemas validated; findings pass the evidence gate before rendering |
| LLM03 | Training Data Poisoning | No fine-tuning on user repos in V1; evaluation harness + regression corpus gate any future model change |
| LLM04 | Model Denial of Service | Risk-adaptive compute, per-tenant daily token ceiling, per-job wall-clock limits, queue backpressure |
| LLM05 | Supply Chain Vulnerabilities | Pinned deps, SBOM, Dependabot, code/secret scanning, pinned analyzer rule packs |
| LLM06 | Sensitive Information Disclosure | Tenant-isolated context assembly; no cross-tenant retrieval; redaction before any trace export |
| LLM07 | Insecure Plugin/Tool Design | Tool allowlists, argument validation, no unrestricted shell, sandboxed execution |
| LLM08 | Excessive Agency | Agents emit hypotheses only; the adjudicator + deterministic verifiers decide; no agent can publish or merge autonomously |
| LLM09 | Overreliance | Evidence gate, confidence filtering, human escalation, citations mandatory on BLOCKING/HIGH |
| LLM10 | Model Theft | N/A for BYOK inference (user's key, provider-hosted model); keys envelope-encrypted, in-memory only |

- **NIST SSDF** — secure development practices in CI.
- **OpenSSF** — supply-chain practices (dependency scanning, secret scanning, SAST, SBOM).

Describe these as engineering baselines/control mappings, not certifications, until formally obtained.

## 5. Credential Breach Response Plan

Per GitHub App security guidance — for each credential class, the play:

| Credential | Detection | Response |
|---|---|---|
| App private key | Audit anomaly, exposed-secret alert | Generate new key → deploy → delete old key (App settings) |
| Webhook secret | Signature failures spike | Rotate secret (app settings + secret manager), redeploy, verify deliveries resume |
| Installation token | Unexpected 401/403, anomalous API calls | `DELETE /installation/token` to revoke immediately; tokens are short-lived, damage bounded |
| User access token / refresh token | Account anomaly | `DELETE /applications/{client_id}/token` to revoke; force re-auth |
| BYOK (user LLM keys) | Any hint of exposure | Immediate re-encryption rotation; notify user; never log the plaintext |

## 6. Vulnerability Reporting

Report security issues privately to the owner via GitHub security advisory on `psyphon1/Meridian` — do not open public issues.
