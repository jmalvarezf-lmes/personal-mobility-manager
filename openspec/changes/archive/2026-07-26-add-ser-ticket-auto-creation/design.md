## Context

`VehicleLocationUpdated` already fans out to two independent, exception-isolated handlers: `NotificationDispatchHandler` (`location_moved`) and `SerTicketTriggerHandler` (`ser_zone_ticket_required`, notification-only — never creates a ticket). `UserPreferences.auto_create_ticket` exists on the entity/API/UI but is currently read by nothing. `DetermineSerTicketRequirement` already folds in enforcement schedule + per-vehicle exemptions + zone eligibility, and `CreateSerTicket` already exists as a full use case (used today only by the manual `POST /parking/ser-tickets` endpoint). `ParkingTicket.end_date` already equals start + duration, so "created until X" needs no new computation.

Two existing repos are relevant to the new validation: `UserSerProviderConfigRepository.list_connected_providers(user_id)` (provider connection check) and `NotificationPreferencesRepository` (cascade target).

## Goals / Non-Goals

**Goals:**
- Wire `auto_create_ticket=true` to actually create SER tickets on qualifying `VehicleLocationUpdated` events, reusing the existing exemption/requirement logic unchanged.
- Keep the three related notification preferences (`ser_zone_ticket_required`, `ser_ticket_created`, `ser_ticket_creation_failed`) mutually exclusive with `auto_create_ticket`'s two states, enforced both as UI grey-out and backend validation.
- Surface success and failure of auto-creation to the user via new, localized, opt-in-by-default (post-activation) notifications.
- Never leak technical exception detail into a user-facing notification.

**Non-Goals:**
- Changing `CreateSerTicket`, `DetermineSerTicketRequirement`, `FindContainingSerZone`, or the manual ticket-creation endpoint's behavior or contract.
- Supporting more than one connected SER provider per user for the auto-creation path (today only `elparking` is ever registered — see Decision 5).
- Retrying failed auto-creation attempts. One `VehicleLocationUpdated` = at most one creation attempt.

## Decisions

### Decision 1: Two handlers, event-mediated handoff, not one branching handler
`SerTicketTriggerHandler` is renamed to `SerTicketNotificationTriggerHandler` and gains a single early exit (`if owner's auto_create_ticket: return`) before its existing preference/zone/notify logic — otherwise unchanged. A new `SerTicketCreationTriggerHandler` is subscribed to the same `VehicleLocationUpdated` event, active only when `auto_create_ticket=true`, and does the zone/exemption check itself before calling `CreateSerTicket`. The two handlers never both do the expensive zone lookup for the same event — the flag routes to exactly one path.

`SerTicketCreationTriggerHandler` publishes `SerTicketCreated` / `SerTicketCreationFailed`; `SerTicketNotificationTriggerHandler` additionally subscribes to both (via two new methods, `on_ticket_created` / `on_ticket_creation_failed`) and is the sole place that calls `SendNotification`. This keeps "decide whether/what to create" and "tell the user about SER-ticket-related things" as two separate responsibilities, consistent with the module docstrings' existing "notification-only" framing for the trigger handler family.

Since `SerTicketNotificationTriggerHandler` now subscribes to three event types on one instance, its pre-existing `handle(event: VehicleLocationUpdated)` method is renamed to `on_vehicle_location_updated`, so all three subscribed methods follow the same `on_<event>` naming convention rather than one being named generically (`handle`) and the other two being named after their specific event. `SerTicketCreationTriggerHandler`'s own `handle(event: VehicleLocationUpdated)` is unaffected — it subscribes to exactly one event type, so `handle` remains unambiguous there (matching `NotificationDispatchHandler`'s existing single-event `handle` convention).

Alternative considered: fold everything into one handler with an `if auto_create_ticket` branch. Rejected — it would mix ticket-creation orchestration and notification-sending in one class, and would require `SerTicketNotificationTriggerHandler` to keep existing as a pure notifier for one code path but not the other.

### Decision 2: `CreateSerTicket` stays exception-based; the new handler translates
`CreateSerTicket.execute()` is not modified — it keeps raising `SerProviderSessionNotFoundError`, `SerZoneNotFoundError`, `SerProviderVehicleNotFoundError`, `SerProviderApiError`, etc., exactly as today. `SerTicketCreationTriggerHandler` catches `Exception` around the call (matching the broad-try/except convention of its siblings — this handler must never break the caller), logs the full exception via `logger.exception` for observability, and publishes `SerTicketCreationFailed` carrying only a small closed-vocabulary `reason: str` (e.g. `"no_provider_session"`, `"vehicle_not_matched"`, `"zone_not_found"`, `"provider_error"`) derived from the exception type — never `str(exc)`. The `ser_ticket_creation_failed` notification template does not interpolate `reason` into user-facing text at all; it renders one generic, localized, friendly message per language ("We couldn't automatically create your SER ticket for zone {{ zone_number }} — please create it manually."). `reason` exists on the event purely for future observability/metrics consumers, not for the notification.

This keeps the manual `POST /parking/ser-tickets` endpoint's HTTP error mapping (`parking.py`) completely untouched — it still catches the same exceptions directly, no new event is published on that path.

### Decision 3: Auto-creation reuses the event's own coordinates and the `ser_zone_ticket_required` row's stored threshold config
`SerTicketCreationTriggerHandler` calls `CreateSerTicket.execute(..., location=GeoLocation(lat=event.latitude, lng=event.longitude))` explicitly — using the coordinates that triggered the check, rather than re-querying `GetLatestVehicleLocation` (avoids a redundant lookup and guarantees the ticket is created for the exact location that was just found inside a zone).

For its own movement-threshold gate (mirroring `SerTicketNotificationTriggerHandler`'s "skip if moved less than threshold since previous location, except on first-ever fix"), it reads the effective threshold from the *same* `ser_zone_ticket_required` preference row's `config.threshold_m` (falling back to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`) even though that row is forced `enabled=false` while `auto_create_ticket=true`. The row keeps existing as the one place per-user movement-threshold config lives for this concern; only its `enabled` flag is locked, not its `config`. Duration comes from `UserPreferences.default_ticket_duration_minutes`; provider from `list_connected_providers(user_id)[0]` (see Decision 5).

### Decision 4: Cascade and validation live in the routers, not a new use-case layer
`preferences.py`'s `update_preferences` and `notification_preferences.py`'s `update_notification_preference` already call injected repositories directly off `request.app.state` (no use-case indirection exists for either endpoint today). This change adds, in the same style:
- `update_preferences`: if `auto_create_ticket` is being set `false → true`, look up `list_connected_providers(current_user.id)`; if empty, 422 ("Connect a SER ticket provider before enabling automatic ticket creation."). On any actual `false → true` or `true → false` transition, cascade-write the three notification-preference rows via `notification_preferences_repo.update(...)` (see table below) *after* the preferences row itself is updated.
- `update_notification_preference`: before delegating to `repo.update(...)`, if `type_key` is one of the three locked types and `body.enabled=true`, look up the caller's current `auto_create_ticket` and reject (422) if the type is currently locked for that state.

| Transition | `ser_zone_ticket_required` | `ser_ticket_created` | `ser_ticket_creation_failed` |
|---|---|---|---|
| `false → true` | forced `enabled=false` | forced `enabled=true` | forced `enabled=true` |
| `true → false` | unlocked (left as-is) | forced `enabled=false` | forced `enabled=false` |

Alternative considered: extract a dedicated `UpdateUserPreferences` / `UpdateNotificationPreference` use case to hold this logic in the application layer. Rejected for this change — neither endpoint has a use-case today, and introducing one here alone would be an inconsistent, unrequested abstraction; revisit if a third caller of this cascade logic appears.

### Decision 5: `SerTicketCreated` carries both `start_date` and `end_date`, formatted into the owner's timezone before rendering
`SerTicketCreated` gains a `start_date: datetime` field alongside `end_date`, so the "ticket created" notification can read "valid from X to Y" rather than just a bare end time. `start_date` is set to `ticket.created_at` — `ParkingTicket` has no dedicated "start" field today, and `created_at` is set immediately after the provider confirms creation (see `ElParkingSerTicketProvider.create_ticket`), which is functionally the moment the parking session begins. The actual `start_date` value sent in the ElParking request body is computed slightly earlier (before the outbound HTTP call) and discarded rather than stored on `ParkingTicket`; reusing `created_at` accepts a sub-request-round-trip discrepancy (typically well under a second) as negligible for a user-facing display value, rather than adding a new persisted column and threading it through the provider port for this alone.

Both `start_date` and `end_date` are UTC-aware `datetime`s on the event. Neither is passed raw into `render()` — `SerTicketNotificationTriggerHandler.on_ticket_created` first converts each into the owner's `UserPreferences.timezone` (falling back to UTC when unset or not a recognized IANA zone) via a new pure helper, `application/datetime_formatting.format_local_datetime(dt: datetime, timezone: str | None) -> str` (stdlib `zoneinfo`, no new dependency), and passes the two resulting strings into the template as `start_date`/`end_date` kwargs. This keeps the Jinja2 templates themselves free of timezone logic — they just interpolate two already-localized strings — consistent with `notification_templates`' stated non-goal of being a general-purpose i18n framework.

Alternative considered: pass the raw `datetime` objects into `render()` and do timezone conversion inside the Jinja2 template via a custom filter. Rejected — it would require registering a custom Jinja2 filter (a new piece of rendering-environment surface) for logic that's simpler as an ordinary Python function called once per notification.

### Decision 6: Single-provider assumption for provider selection
`SerTicketCreationTriggerHandler` picks `list_connected_providers(user_id)[0]` deterministically (list order from the repository). Today `SerTicketProviderRegistry` only ever registers `elparking`, so in practice this is always exactly one connected provider once the Decision-4 validation has passed. If the provider was connected at validation time but has since been disconnected (`list_connected_providers` now empty), the handler treats this the same as any other creation failure — publishes `SerTicketCreationFailed` with `reason="no_provider_session"` — rather than adding a reconciliation step to `DisconnectSerTicketProvider`. Multi-provider selection is an explicit non-goal (see above); revisit when a second provider is registered.

## Risks / Trade-offs

- **[Risk]** A user could interpret "auto ticket creation failed" notifications as noisy if their provider session lapses and they keep driving into SER zones. → **Mitigation**: it's opt-in (`ser_ticket_creation_failed` is itself a togglable preference, just default-on), and each failure is still one notification per qualifying `VehicleLocationUpdated`, same cadence as the obligation notice it replaces.
- **[Risk]** `ser_zone_ticket_required`'s config (`threshold_m`) becomes implicitly shared state between two features (its own notification and the auto-creation gate) — a future change to one could silently affect the other. → **Mitigation**: documented in Decision 3 and in the handler's docstring; both consumers are already in this codebase's established "resolve_effective_threshold per preference row" pattern.
- **[Risk]** Migration must retroactively enforce the new invariant for any user who already has `auto_create_ticket=true` (the checkbox existed and was persistable before this change, even though nothing read it). → **Mitigation**: see Migration Plan.

## Migration Plan

1. Alembic migration: insert two new `notification_types` rows (`ser_ticket_created`, `ser_ticket_creation_failed`), empty `config_schema`, following `p3q4r5s6t7u8_create_notification_types.py`'s `bulk_insert` pattern.
2. Data migration: backfill `user_notification_preferences` for the two new types, `enabled=false, config={}` for every existing user, `ON CONFLICT DO NOTHING` — same idempotent pattern as `r5s6t7u8v9w0_backfill_user_notification_preferences.py`.
3. Data migration (same or follow-up revision): for every user where `user_preferences.auto_create_ticket = true`, `UPDATE user_notification_preferences SET enabled = true WHERE type_key IN ('ser_ticket_created', 'ser_ticket_creation_failed')` and `SET enabled = false WHERE type_key = 'ser_zone_ticket_required'`, scoped to those users only — retroactively enforces the invariant for anyone who already had the flag on before it did anything.
4. Deploy code (handler rename + new handler + new events + router validation/cascade) after migrations are applied, since `app.py` wiring references the new handler classes and the routers reference the two new type keys.
5. Rollback: reverting code is safe without reverting the migrations (extra catalog rows / preference rows are simply unused by old code). No down-migration is provided for the data backfill, matching the existing precedent's rationale.

## Open Questions

None outstanding — all forks raised during exploration were resolved with the user before this design was written.
