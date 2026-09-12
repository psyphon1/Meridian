# Meridian — Deployment & Operations

**12-factor principles throughout:** config strictly separated from code (env vars, granular and orthogonal — never "environment groups"), backing services attached via URLs, stateless processes, disposability. Infrastructure: Docker → Kubernetes (base + overlays) provisioned by Terraform (dev/staging/production).

---

## 1. Environments

| Env | Purpose | Data | Stability bar |
|---|---|---|---|
| dev | Local per-developer | Fixtures/seeds | Unstable |
| staging | Pre-prod integration, deletion drills, benchmark runs | Synthetic only, no real keys | Mirrors prod config |
| production | Live app | Real tenant data, real BYOK keys | Full SLOs |

Staging must be **production-shaped** (same container images, same K8s overlays modulo scale/limits) so the blue-green switch (§3) is exercised on every release.

## 2. Build & Deploy Pipeline

1. PR → CI: lint, typecheck, unit + integration tests, SAST (CodeQL), secret scan, SBOM generation (OpenSSF-aligned).
2. Merge to `main` → build immutable, digest-pinned container images (one image per app; no `latest`).
3. Deploy to staging automatically; run evals + regression benchmark (`evals/`) as a gate.
4. Promote the **same image digests** to production (never rebuild) — deployment is promotion, not compilation.

## 3. Rollout Strategy: Blue-Green

Two production environments (blue/green), as identical as possible; the router switches traffic between them:

- Final staging pass happens in the **idle** environment; switch the router to promote it live; the previous env becomes rollback target.
- **Rollback = flipping the router back** — drilled every release (same mechanism as hot-standby DR).
- **Database migrations are decoupled from app upgrades** (per Fowler): first apply expand-migrations compatible with both app versions, deploy app, verify, then contract (remove old columns/tables) in a later release. This keeps blue-green viable with a shared database.
- Workers drain their Redis Streams consumer groups before the old env is retired (`XACK`-clean shutdown); the janitor `XAUTOCLAIM` resumes any pending work on the new env.

## 4. Runtime Topology

- **api** (FastAPI): stateless, HPA on RPS/CPU; webhook endpoint only does verify→persist→enqueue.
- **worker**: consumer-group consumers; HPA on Redis stream depth (saturation signal); graceful drain on SIGTERM.
- **web** (Next.js): static-first, CDN-cached.
- **services**: indexer, evidence, notification, audit — independently scalable; audit-service owns the separate append-only audit store.
- **sandbox pool**: pre-warmed, per-tenant namespace, strictly rate-limited provisioning.

## 5. Release Checklist

- [ ] Backward-compatible migrations applied first
- [ ] Green env health: SLO dashboards clean for 30 min post-switch
- [ ] Webhook deliveries flowing (check `X-GitHub-Delivery` cursor + GitHub delivery log)
- [ ] Old env kept warm for ≥ 1 hour as instant rollback
- [ ] Audit log records the deploy event (config change)

## 6. Rollback & Incident

Rollback = router flip (≤ 1 min). If the database is implicated, forward-only fix + feature flag off is preferred over down-migrations. Incidents get a blameless postmortem within 48 h; every silent-drop-class bug is a P0 (the system promises no silent drops).
