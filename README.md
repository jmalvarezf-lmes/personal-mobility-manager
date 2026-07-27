<p align="center">
  <img src="frontend/public/logo.png" alt="Personal Mobility Manager logo" width="220" />
</p>

# Personal Mobility Manager

Stop paying Madrid SER parking fines because you forgot to buy a ticket. This
tracks your vehicle, knows when you've parked inside a regulated zone during
enforcement hours, and — if you've connected a provider — buys the ticket for
you automatically. I built this becase my wife and I are constantly forgetting the placement
of ser tickets, because we live in a very stressful world, and we have kids
to take care of. Such is the case that I had to add a yearly budget for fines. 
This development addresses this need, so that, with luck, I don't have to pay 
absurd fines anymore.

## What it does

You sign in with Google and register a vehicle: either a Toyota, connected
through `pytoyoda` so the app can pull its GPS location on a schedule, or a
"generic" device — anything that can POST coordinates to a per-vehicle
push-token endpoint (a phone running GPS Logger, an ESP32, a Tasker profile,
whatever you've got). From there the system watches that vehicle's location
continuously.

Madrid publishes its SER (Servicio de Estacionamiento Regulado) zone
boundaries as shapefiles. This ingests them, resolves each zone's street,
district, and enforcement calendar, and stores the polygons in Postgres.
When a new location update comes in, a spatial join checks it against those
polygons — not a rough radius check, an actual point-in-polygon containment
test (with a small tolerance to absorb GPS error) — to decide whether the
vehicle just crossed into or out of a SER zone. That zone-transition check,
not raw distance moved, is what triggers everything downstream, so a car
that's been sitting still doesn't get re-evaluated on every noisy GPS ping.

A zone entry during enforcement hours raises a domain event. Handlers
subscribed to that event check exemptions (a manual per-vehicle override, or
an automatic one for vehicles carrying the DGT electric/eco label), and if a
ticket is actually owed and the user has connected a ticket-purchasing
provider, place the purchase and record the result. Every step along the way
— zone entry, ticket created, ticket failed — fires a Telegram notification,
because the entire point is that you don't have to think about it.

Underneath, this is built as strict Clean/Hexagonal Architecture: domain
entities and value objects with zero framework dependencies, use cases that
depend only on abstract ports, and SQLAlchemy/FastAPI pushed out to the
infrastructure and presentation layers. That's not decoration — it's what
lets city, ticket-provider, vehicle-brand, and notification-channel support
be added as isolated adapters behind a registry (more on that below) instead
of forking core logic. Coverage gates enforce it: 100% on `domain/`, 80%+ on
`application/`. CI runs the backend test suite against a real Postgres
service container (not mocks) and the frontend's Playwright suite against a
live backend + Postgres, so the E2E layer is exercising the real stack, not
a facsimile of it.

## Live environment

A running instance is deployed at
[www.personal-mobility-manager.com](https://www.personal-mobility-manager.com),
built from the same Docker images the release workflow publishes on tagged
releases.

## Tech stack

**Backend** — Python 3.14, FastAPI, SQLAlchemy + Alembic for migrations,
PostgreSQL 16. Google OAuth2 via Authlib with PyJWT-signed session cookies.
APScheduler drives the background jobs (location polling, SER zone
ingestion, ambient-label lookups, session cleanup, public-holiday refresh).
pyproj/shapely/pyshp handle the geo work — shapefile parsing and the
spatial joins behind zone-containment checks. `cryptography` (Fernet)
encrypts stored Toyota and ElParking credentials at rest. slowapi does rate
limiting, jinja2 renders notification templates, icalendar handles public
holidays, httpx is the outbound HTTP client. OpenTelemetry is wired in but
inert unless `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

**Frontend** — React 19, TypeScript, Vite 8, Tailwind CSS 4, React Router 7.
Leaflet + react-leaflet for the maps, i18next for translations,
swagger-ui-react to render the live OpenAPI docs in-app. Package management
via pnpm.

**Infra & CI** — Docker Compose for local/self-hosted running (Postgres +
API + nginx-fronted frontend). GitHub Actions runs lint (ruff, mypy strict,
tsc, eslint) and the full test matrix (backend against a real Postgres
service container; frontend unit tests plus Playwright E2E) on every PR. A
separate release workflow builds and pushes versioned images to GHCR
(`ghcr.io/jmalvarezf-lmes/personal-mobility-manager-backend` and
`-frontend`) on `v*.*.*` tags.

## Sessions

Login is Google OAuth2, but authorization afterward doesn't rely on the JWT
alone. `POST /auth/google/callback` creates a server-side `Session` row
(`user_id`, `created_at`, `expires_at`, `revoked_at`) and issues a JWT whose
`sid` claim points at it, set as an `httponly`, `secure`, `samesite=strict`
cookie with a 24-hour `max_age` matching the session's own lifetime
(`SESSION_LIFETIME` in `config.py` — one source of truth for both). Every
authenticated request validates the session, not just the JWT signature: the
session must exist, be unexpired, unrevoked, and owned by the token's user —
so `POST /auth/logout` can actually kill a session server-side instead of
just clearing a cookie the client could otherwise keep replaying. A
scheduled job (`CleanupExpiredSessions`) purges expired/revoked rows past a
retention window so the table doesn't grow unbounded.

## API

The API is mounted under `/api` (nginx proxies it to the backend service).
Resource groups: auth (Google OAuth login/callback/session), vehicles (CRUD,
latest location, location history, the public push-ingest endpoint for
generic devices, per-vehicle SER exemptions), parking (nearest SER zone
lookup, ticket creation), zones (GeoJSON zone data for the map, a
lightweight zone-options list), cities, config (runtime frontend config),
preferences and notification-preferences, notifications (Telegram linking
and webhook), ser-ticket-providers (connect/list/disconnect a
ticket-purchasing account), ambient-labels, and a health check.

The authoritative, always-current contract is the auto-generated OpenAPI
spec — browse it as Swagger UI at
[personal-mobility-manager.com/api-docs](https://www.personal-mobility-manager.com/api-docs)
on the live instance, at `/api-docs` locally, or fetch the raw document from
`/api/openapi.json`. This README won't try to keep a hand-written endpoint
list in sync with that.

## Running it locally

Requires Docker and Docker Compose.

```bash
git clone <this-repo>
cd personal-mobility-manager
cp .env.example .env
```

Edit `.env`. At minimum you need Google OAuth credentials to be able to log
in at all:

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:3000/api/auth/google/callback
JWT_SECRET=...          # python -c "import secrets; print(secrets.token_hex(32))"
ENCRYPTION_KEY=...      # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`ENCRYPTION_KEY` is technically only required when a Toyota vehicle or the
ElParking SER provider is enabled — but ElParking is enabled by default
(`ENABLED_SER_PROVIDERS=elparking`), so in practice every deployment needs
it set.

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, and `TELEGRAM_BOT_USERNAME`
are required too: the Telegram channel is constructed unconditionally at
startup. Create a bot via `@BotFather` to get a token, then register a
webhook (Telegram's `setWebhook` API) with a `secret_token` matching
`TELEGRAM_WEBHOOK_SECRET`.

Everything else in `.env.example` is optional and degrades gracefully:

- `TOYOTA_USERNAME` / `TOYOTA_PASSWORD` — leave unset and Toyota vehicle
  polling simply isn't available; you can still register a generic
  push-token device.
- `ELPARKING_API_BASE_URL` — required only if you keep ElParking enabled
  (the default); without it, auto-ticket purchasing has nothing to call.
- `OTEL_EXPORTER_OTLP_ENDPOINT` — leave empty and observability is fully
  inactive, zero overhead.
- `SER_ZONE_SHP_URL`, `MADRID_CALLEJERO_URL`, `MADRID_BARRIOS_SHP_URL` — have
  working defaults pointing at Madrid's open-data portal; only override if
  you're standing up a different data source.

Then:

```bash
docker compose up
```

This starts Postgres, the API (migrations run automatically via
`docker-entrypoint.sh` before the server starts — no manual `alembic
upgrade` step needed), and the nginx-fronted frontend. Reach the app at
`http://localhost:3000`; the API alone is reachable directly at
`http://localhost:8000`.

### Map tiles

The zone map (`/map` in the frontend) requests its tile source from the
backend's `GET /config` endpoint, which returns the `OSM_TILE_URL`
environment variable as-is. If you leave `OSM_TILE_URL` unset, the frontend
falls back to the public OpenStreetMap tile server
(`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`) — fine for casual
local testing, but OSM's own tile usage policy does not permit sustained or
production traffic against it.

To point at a different tile provider, set `OSM_TILE_URL` in `.env` to any
XYZ tile URL template. There is currently no self-hosted tile server wired
into `docker-compose.yml` — if you want one (e.g. a `tileserver-gl` or
similar image serving locally-downloaded MBTiles), you'd add it as its own
service in `docker-compose.yml` and point `OSM_TILE_URL` at that service's
address instead. That's on you to wire up; it isn't provided out of the box.

Note: this configurable tile URL only feeds the zones map
(`ZoneMap.tsx`, via `MapPage.tsx`). The per-vehicle location maps
(`VehicleMap.tsx`, `VehicleLocationHistoryModal.tsx`) currently hard-code the
public OSM tile URL regardless of `OSM_TILE_URL`.

## Integrations implemented so far

The architecture is deliberately registry/port-based specifically so more of
each of these can be added without touching core logic. Here's what's
implemented today, and where to plug in a new one:

- **Cities** — only Madrid. The `cities` DB table is the source of truth for
  which cities are active; `infrastructure/parking_services/provider_registry.py`
  looks up a `CityParkingDataProvider` implementation per registered city
  code, and only Madrid has one
  (`MadridSerStreetsProvider`, under `infrastructure/parking_services/madrid/`).
  Adding a city means seeding a `cities` row, implementing the port, and
  registering it there.
- **SER ticket providers** — only ElParking
  (`infrastructure/ser_ticket_providers/elparking/`), selected via the
  `ENABLED_SER_PROVIDERS` env var and looked up through
  `infrastructure/ser_ticket_providers/registry.py`, which currently only
  recognizes the code `elparking`. Adding a provider means implementing
  `SerTicketProviderPort` and registering it in that registry.
- **Vehicle location sources** — Toyota (pull-based, via `pytoyoda`) and a
  brand-agnostic "Generic" push-token HTTP endpoint that works with any
  device capable of POSTing GPS coordinates. Adding a new brand means
  implementing the vehicle-provider port
  (`domain/ports/vehicle_provider.py` / `vehicle_pull_location_port.py`)
  under `infrastructure/vehicle_providers/`.
- **Notification channels** — only Telegram
  (`infrastructure/notification_channels/telegram/`). The port
  (`domain/ports/notification_channel.py`) is deliberately a single abstract
  method, `send(recipient, message)`, so email, SMS, push, or webhook
  channels can be added by implementing that port and registering the
  adapter in `presentation/api/app.py`'s startup wiring.

## Development / contributing

See [`AGENTS.md`](./AGENTS.md) for the Clean Architecture rules, test
pyramid, and coverage gates (100% `domain/`, 80%+ `application/`) this
project holds itself to, plus the OpenSpec-based change workflow used for
non-trivial changes. It's the source of truth — this README won't duplicate
it.
