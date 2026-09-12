# Meridian

> **The autonomous first-pass engineer for every GitHub pull request.**

Meridian automatically performs the first senior-level PR investigation for every GitHub pull request — using repository-wide context, specialized AI reasoning and verifiable evidence — then publishes the review and escalates only the decisions that still require human judgment.

**Owner:** Chinmay Duse ([psyphon1](https://github.com/psyphon1)) · [LinkedIn](https://linkedin.com/in/chinmayduse)

## What it does

```
PR opened/updated
  → webhook (verified, idempotent)
  → durable queue
  → intent + risk classification
  → repository-aware retrieval
  → conditional specialized review agents
  → evidence verification (Semgrep / CodeQL / sandbox)
  → evidence-gated publish
  → GitHub review with SHA-pinned citations
  → human escalation only where judgment is needed
```

## Documentation

See [`docs/README.md`](docs/README.md) for the full documentation index.

- [Product Requirements (PRD)](docs/PRD.md)
- [System Design (SDD)](docs/SDD.md)
- [Technical Requirements (TRD)](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Security](docs/SECURITY.md)
- [Roadmap & status](track.md)

## Status

🚧 **Design phase → build starting.** Repository structure and documentation are in place; implementation follows the phase plan in [`docs/TRD.md`](docs/TRD.md).

## License

MIT — see [LICENSE](LICENSE).
