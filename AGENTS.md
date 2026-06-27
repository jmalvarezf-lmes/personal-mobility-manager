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

## Madrid Callejero CSV — Key Facts

The reference file is `200075-1-callejero-csv.csv` (215 k rows, Latin-1, semicolon-delimited, all fields quoted).

| Role | Column name |
|---|---|
| Street name | `Nombre de la vía` |
| SER zone code | `Zona Servicio Estacionamiento Regulado` |
| UTM easting (cm) | `Coordenada X (Guia Urbana) cm` |
| UTM northing (cm) | `Coordenada Y (Guia Urbana) cm` |

- Zone code `"000"` means no SER zone — skip those rows.
- X/Y values are in **centimetres**; divide by 100 for EPSG:25830 metres.
- Distance calculation uses **UTM Euclidean distance** (not Haversine).
- Fetcher must decode response bytes as `latin-1`.

---

## Python Skill

When implementing any Python feature, endpoint, use case, repository, or domain model, load and follow the `python-clean-arch` skill at `~/.claude/skills/python-clean-arch/SKILL.md`.

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
