# Agent Rules — personal-mobility-manager

## Test Gate (mandatory)

**Run the full test suite after every code change. A change is NOT done until all tests pass.**

```bash
make test
```

- All non-integration tests must pass before reporting a task complete.
- Integration tests (`test_ser_zone_repo_integration.py`) require `POSTGRES_DSN` to be set; they are skipped automatically when the env var is absent — that is acceptable.
- Never modify production code and skip test verification. Never mark work done while tests are red.

---

## Clean Architecture — Hard Rules

This project follows strict Clean Architecture. Layer imports flow inward only:

```
Domain  ←  Application  ←  Infrastructure  ←  Presentation
```

| Layer | Allowed imports |
|---|---|
| Domain | stdlib only — no framework, no ORM, no library |
| Application | Domain + stdlib |
| Infrastructure | Application + ORM/DB libs (SQLAlchemy, psycopg2, pyproj, httpx) |
| Presentation | Application + FastAPI |

**Hard violations (never do these):**
- A domain entity importing SQLAlchemy, FastAPI, or any library.
- A router importing a repository or ORM model directly.
- A use case importing anything from Infrastructure.

---

## Test Pyramid

| Type | Scope | Target share |
|---|---|---|
| Unit | Domain logic + use cases with mocked ports | 70% |
| Integration | Repository adapters against a real DB | 20% |
| E2E | Full HTTP flow via FastAPI `TestClient` | 10% |

New features must include tests at each applicable level. Use `unittest.mock` for ports in unit tests. Integration tests live in `tests/infrastructure/` and must be skippable without `POSTGRES_DSN`.

## Coverage Targets (mandatory)

| Layer | Minimum coverage |
|---|---|
| `domain/` | **100%** — entities, value objects, exceptions, ports |
| `application/` | **80%** — use cases |

Run with `make coverage` (or `pytest --cov=src/mobility_manager --cov-report=term-missing`). A change is not done if it drops either layer below its target.

---

## Project Layout

```
src/mobility_manager/
    domain/
        entities/          # Pure Python dataclasses — no deps
        value_objects/     # Immutable, equality by value
        exceptions.py
        ports/             # ABCs — abstract repository/service interfaces
    application/
        use_cases/         # One class per use case; depends only on ports
    infrastructure/
        parking_services/madrid/   # CSV fetcher + parser
        repositories/postgres/     # SQLAlchemy implementations of ports
        scheduler.py
        db.py
    presentation/
        api/routers/       # FastAPI routers — call use cases only
        api/schemas.py     # Pydantic response models
        cli/

tests/
    domain/                # Unit — pure logic
    application/           # Unit — use cases with mocked ports
    infrastructure/        # Integration — real DB required (skippable)
    presentation/          # E2E — TestClient
```

---

## Python Skill

When implementing any Python feature, endpoint, use case, repository, or domain model, load and follow the `python-clean-arch` skill at `~/.claude/skills/python-clean-arch/SKILL.md`.

---

## Makefile consistency (MANDATORY)

Any change to how a task is executed — test command, coverage command, migration, server start, linting, formatting, or any other workflow step — must also update the `Makefile` to keep it the source of truth for all runnable operations.

Do not leave the `Makefile` stale. If a new tool is added, a flag changes, or a step is renamed, update the relevant `make` target in the same commit.

---

## OpenSpec: Git branch per change (MANDATORY)

Every time a new OpenSpec change is created — whether via `/opsx:propose`, `/sdd-new`, or any other command that calls `openspec new change "<name>"` — immediately create and check out a git branch named `change/<name>` before writing any artifacts.

```bash
git checkout -b change/<name>
```

This rule is non-negotiable. Do not skip it, do not ask for confirmation — create the branch as part of the change creation flow.

---

## OpenSpec: Create a PR on archive (MANDATORY)

Every time an OpenSpec change is archived — via `/opsx:archive` or any equivalent command that moves a change to `openspec/changes/archive/` — immediately create a pull request targeting `main` after the archive step completes.

Use the `branch-pr` skill (`~/.claude/skills/branch-pr/SKILL.md`) to create the PR. The PR title should follow the pattern `change: <change-name>` and the body should summarise what was implemented, referencing the proposal and any specs that were synced.

This rule is non-negotiable. Do not skip it, do not ask for confirmation — create the PR as part of the archive flow.
