## Context

Spain's DGT (Dirección General de Tráfico) assigns every vehicle one of five environmental labels — A (none), B, C, ECO, 0 — used to gate entry to low-emission zones. DGT does not offer an official API for this; it offers a public HTML form at `sede.dgt.gob.es/.../distintivo-ambiental/index.html?matricula=<plate>`.

A pre-proposal spike (see conversation history, not a file) confirmed the mechanics directly against the live site with a real, owned plate:

- The form's `action` has no `method` attribute, so it submits via GET. `curl`-ing the URL directly with `?matricula=<plate>` returns a fully server-rendered result — no JS/AJAX round-trip, no CAPTCHA on this path.
- Three distinct response shapes were observed, keyed by container class:
  - `class="border rounded border-success ..."` → label found. Contains an `<img src=".../distintivo_B_sin_fondo.svg">` (letter embedded in the filename) and prose `<strong>Distintivo Ambiental B.</strong>` — two independent, cross-checkable signals for the same letter.
  - `class="alert alert-warning ..."` with text "Sin distintivo. Tu vehículo no cumple los requisitos..." → confirmed category A (no label). This is a genuine, confident terminal result, not an error.
  - `class="alert alert-danger ..."` with text "No se ha encontrado ningún resultado..." → plate not found in DGT's system, or possibly a transient/blocked query. Not a confident terminal result.
- `robots.txt` doesn't disallow this path but explicitly blocks dozens of known scraper user-agents by name and sets `Crawl-delay: 20` for bots it does allow — a clear signal DGT cares about automated load even though it doesn't forbid this specific lookup.

This is an **unofficial, unversioned dependency on a government form**, not a stable API. The design treats it accordingly: isolated behind a port, never trusted to be available or stable, and never allowed to affect the user-facing registration flow.

The existing codebase already has two precedents for "poll external source, isolate failures, don't let one bad item break the run": `ParkingIngestionScheduler` (recurring full resync per city) and `VehicleLocationScheduler` (recurring per-vehicle poll, per-item try/except + span, `BackgroundScheduler`). This feature is closer to a **backlog-drain** job than either: it targets only vehicles missing a confident result, not all vehicles every tick.

## Goals / Non-Goals

**Goals:**
- Resolve each vehicle's DGT environmental label automatically from its license plate, with no user action required.
- Never let DGT's availability, latency, or markup affect vehicle registration or any other request path.
- Be a polite, low-volume client: throttle to one request per 5 seconds, only query vehicles that actually need it, back off on inconclusive results instead of retrying every cycle.
- Distinguish confidently-terminal results (A/B/C/ECO/0 — never re-checked) from inconclusive ones (not-found/parse-error — retried later) so the backlog doesn't refill with a fixed set of dead plates forever.

**Non-Goals:**
- Re-validating an already-resolved label later (DGT categorizations can theoretically change, e.g. retrofits — out of scope; a future change can add periodic re-validation if it turns out to matter).
- A user-facing "re-check now" action/endpoint.
- Any UI treatment (icon, color badge) beyond exposing the raw field on read endpoints — left to a follow-up if wanted.
- Handling a CAPTCHA or JS challenge, should DGT add one later (falls into the "error" bucket like any other break; no proxy/IP-rotation/browser-automation infrastructure is in scope).
- Looking up plates for vehicles the user doesn't own (the feature only ever queries plates already stored against the authenticated user's own vehicles).

## Decisions

**1. Separate `vehicle_ambient_labels` table, not columns on `vehicles`.**
1:1 with `vehicles`, keyed by `vehicle_id`. Mirrors the existing `vehicle_configs` pattern. Keeps the core `Vehicle` entity free of polling/lookup bookkeeping (`status`, `last_checked_at`) that has nothing to do with vehicle identity, and leaves room to add lookup history later without touching the entity.

Columns: `vehicle_id (PK, FK→vehicles.id, ON DELETE CASCADE)`, `label (varchar, nullable)`, `status (varchar: found|not_found|error)`, `last_checked_at (timestamptz, nullable)`.

The FK must be created with `ON DELETE CASCADE` directly in this table's own creation migration (unlike `vehicle_configs`/`vehicle_locations`, which needed a separate retrofit migration — `a7b8c9d0e1f2` — because they predated that convention). `DeleteVehicle`/`PostgresVehicleRepository.delete()` rely entirely on DB-level cascade with no application-code cleanup of child tables, so a missing `ondelete="CASCADE"` here means every vehicle delete with a resolved ambient label fails on the FK constraint.

**2. Three-way status, not a boolean "resolved" flag.**
`found` is terminal — the scheduler's backlog query excludes it permanently. `not_found` and `error` both represent "we don't have a confident answer" and are retried after a cooldown. They're modeled as separate values (not collapsed into one "unresolved") purely for observability — the metric distinguishes "DGT says no record" from "our request/parse failed" without changing retry behavior, since neither is trustworthy enough to treat as an answer, per the spike finding that DGT's own "not found" page can't be told apart from a transient hiccup.

**3. Parse by container class first, letter second.**
Branch on the wrapping `<div class="...">` (`border-success` / `alert-warning` / `alert-danger`) rather than matching on Spanish prose text as the primary signal — copy can change wording without changing the class DGT uses to drive the alert's visual style. Within the success branch, extract the letter from the image filename (`distintivo_(A|B|C|ECO|0)_`) and cross-check against the `<strong>Distintivo Ambiental X</strong>` text; if the two disagree, treat the result as `error` (markup drift) rather than trusting either — a silently wrong label is worse than a retried lookup.

**4. Best-effort trigger at registration, scheduler as the only durable retry path.**
`RegisterVehicle.execute()` calls the lookup provider synchronously but wraps it in try/except that only logs — registration always succeeds/fails independently of DGT. This mirrors the "never block the caller" resilience pattern already used for scheduler ticks, applied here to a request path instead of a background job. The scheduler is not just a fallback for scale — it's the only place retries and backoff live; registration never retries.

Because the lookup is synchronous, the result is already persisted by the time `POST /vehicles`'s response is built — so that response resolves the label the same way `GET /vehicles`/`GET /vehicles/{id}` do (via the same `_resolve_ambient_label` read-back helper in the router, not a value threaded through `RegisterVehicleResult`), rather than omitting it the way it omits other fields the registration flow genuinely doesn't compute synchronously (e.g. `location`). Omitting it here would force every client to make a redundant follow-up read for data that already exists.

**5. Scheduler is a backlog-drain job, not a full-resync job.**
Unlike `ParkingIngestionScheduler`/`VehicleLocationScheduler` (both re-poll their entire target set every tick), this scheduler's tick queries only vehicles with a plate set AND (`no row yet` OR (`status != found` AND `last_checked_at` older than the cooldown)). A 5-second `time.sleep()` between consecutive lookups (not after the last one) throttles the run; `BackgroundScheduler`'s default `max_instances=1` per job id prevents overlapping runs if a backlog takes longer than the tick interval to drain.

**6. New config knobs, env-var driven with defaults, following the existing `config.py` convention (`os.environ.get(NAME, "default")` + `int()` with a fallback on parse failure, same shape as `get_vehicle_poll_interval_minutes()`):**
- `get_ambient_label_poll_interval_minutes()` ← `AMBIENT_LABEL_POLL_INTERVAL_MINUTES`, default `60`
- `get_ambient_label_retry_cooldown_hours()` ← `AMBIENT_LABEL_RETRY_COOLDOWN_HOURS`, default `24`
- `get_ambient_label_request_delay_seconds()` ← `AMBIENT_LABEL_REQUEST_DELAY_SECONDS`, default `5`

All three are unset-safe (deployments that don't set them get the defaults above unchanged) and mainly useful for tuning post-deploy or lowering the delay in tests.

**7. Hostname-allowlist + fixed-URL provider, same shape as `MadridCallejeroCsvFetcher`, with a browser-like User-Agent.**
`DgtAmbientLabelProvider` validates the configured base URL's hostname is `sede.dgt.gob.es` at construction time, and passes the plate as an httpx `params` value (never string-concatenated into the URL) so it's properly encoded — no injection surface, since the endpoint and path are fixed and only the query value varies. The client sends a standard browser `User-Agent` (not a custom/descriptive one) — traffic volume here is low (one request per vehicle needing a lookup, throttled to 5s apart) and the goal is a reliable response, not scraper transparency; `robots.txt`'s named-bot blocklist targets known scraping tools by user-agent string, which this avoids by construction.

**8. Icon cached once per label value, not once per vehicle.**
Only 5 label values exist and only 4 of them (B, C, ECO, 0) have a physical sticker image at all — category A's DGT response (the `alert-warning` branch) contains no `<img>`, since there's nothing to depict. The parser already extracts the icon's relative URL as part of resolving B/C/ECO/0 (same regex that extracts the letter from the filename). When a lookup resolves one of those four labels, the icon cache is checked by label value; on a cache miss, the icon is downloaded once (via the same hostname-allowlisted HTTP client, resolving the relative path against `sede.dgt.gob.es`) and stored keyed by label — every subsequent vehicle sharing that label reuses the cached bytes. This avoids N redundant downloads of an identical image for N vehicles with the same label, and keeps the DGT request budget spent on resolving labels, not re-fetching static assets.

**9. Icons are proxied through our own API, not hotlinked.**
`GET /ambient-labels/{label}/icon` serves the cached bytes with the correct `Content-Type` and a long-lived `Cache-Control` (the image for a given label is immutable once cached). The frontend never embeds a `sede.dgt.gob.es` URL directly — this avoids every user's browser depending on DGT's asset hosting/paths staying stable, and avoids DGT seeing per-user image request traffic for something we've already cached. The endpoint is unauthenticated: the image content is identical for every user and carries no per-vehicle or per-user information (just "what does a Category B sticker look like"), so gating it behind auth would add friction with no confidentiality benefit. Requesting the icon for label A, or for a label not yet cached (no vehicle has resolved to it yet), returns 404 — the frontend treats a 404 the same as "no icon available" and falls back to a text/label-only indicator.

**10. `AmbientLabelIcon` follows the existing i18n contract; e2e coverage lives alongside the existing vehicle card tests.**
Per `openspec/specs/ui-i18n/spec.md`, every vehicle-facing component's strings go through `t()` — this change adds `AmbientLabelIcon` to that component's list (delta in `specs/ui-i18n/spec.md`) rather than treating a few words ("no label", an icon's alt text) as too small to bother translating. E2E coverage is added to the existing `frontend/e2e/my-vehicles.spec.ts` (extending its `mockVehicleApis` fixture and vehicle-card describe blocks) rather than a new spec file, since it's testing an addition to the same page and card component already covered there.

## Risks / Trade-offs

- **[Risk] DGT changes the page's markup, silently breaking the parser.** → Mitigation: cross-check the two independent signals (filename + prose) in the success branch; log and count `error` distinctly in a metric so drift is visible in dashboards rather than silently returning wrong data.
- **[Risk] DGT rate-limits or blocks the app's IP for automated traffic.** → Mitigation: 5s delay between requests, backlog-only querying (never full resync), cooldown before retrying inconclusive results. Accepted residual risk: this is inherent to automating a form not built for this; if DGT starts blocking outright, the feature degrades to "labels never resolve," which is a soft failure (nullable field), not an outage.
- **[Risk] Automated querying sits in a legal/ToS gray area for a government service.** → Not a code-level mitigation: scope is deliberately narrow (only the user's own registered vehicles, never bulk/third-party lookups, low volume, throttled). Called out here as an accepted product decision, not resolved by design.
- **[Trade-off] No re-validation of already-found labels.** → Accepted per Non-Goals; a vehicle whose DGT category changes post-lookup will show a stale label until a future change adds re-validation.
- **[Risk] Icon endpoint is unauthenticated.** → Accepted: content is non-sensitive and identical for every caller (a static government sticker image), so this trades a theoretical minor scraping surface (someone could enumerate all 4 icons without logging in) for simpler frontend embedding. Not a concern since the same images are public on DGT's own site.

## Migration Plan

1. Alembic migration adds `vehicle_ambient_labels` table (additive only, no changes to existing tables).
2. Deploy provider + scheduler; both are additive and off the request path — no feature flag needed, since worst case on DGT failure is "field stays null," identical to today's behavior.
3. Rollback: revert the migration (drops the new table only) and stop the scheduler; no data loss beyond the lookup cache itself, which is always re-derivable from DGT.

## Open Questions

- Default values for the three config knobs (interval: 60min / cooldown: 24h / delay: 5s) are settled as ship defaults but not load-tested against DGT's actual tolerance — may need adjustment post-deploy based on observed error rates, which is exactly what the env vars are for.
