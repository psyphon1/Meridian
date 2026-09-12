# Meridian — Code Standards

**Per v2 spec §41 and the design doc's engineering standards.**

## Python (API, worker, services, packages)

- Type hints (strict where practical); explicit error handling; PEP 8.
- **Ruff** for lint + format; **pytest** for tests; **mypy**-checked typing on domain contracts.
- Explicit, consistent exception types — no bare `except:`.

## TypeScript (web dashboard)

- **Strict mode** TypeScript; **ESLint** + **Prettier**; component/unit tests for UI behavior.

## API

- OpenAPI contract; versioned endpoints; consistent error envelopes; no secrets in error messages.

## Git

- Protected `main`; **Conventional Commits**; CI-required PRs; `CODEOWNERS` enforcement.

## Security tooling in CI

Dependency scanning · secret scanning · SAST · SBOM generation.

## Testing rule

Behavior changes include tests. Production bugs get regression tests where practical.
