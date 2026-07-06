## Context

`NotificationDispatchHandler` has been an inert subscriber to `VehicleLocationUpdated` since `add-telegram-notification-channel`, deliberately widened "little by little." `add-notification-channel-ui` gave users a UI to connect a channel and pick `preferred_notification_channel`, but nothing calls `SendNotification` in production yet. This change makes the first real notification kind — vehicle movement — actually fire, without deciding per-event-type opt-in/opt-out (deferred) and without building a general notification-templating framework (only two message kinds exist: vehicle-moved, and the existing Telegram-link confirmation).

`RecordVehicleLocation.execute` saves the new `VehicleLocation` row *before* publishing `VehicleLocationUpdated`, so by the time any subscriber runs, `VehicleLocationRepository.get_latest(vehicle_id)` returns the row that just triggered the event, not the one before it. Any movement-distance comparison needs a different query.

`ser_zone_repo.py` already has a `distance_m(lat1, lng1, lat2, lng2)` helper (UTM Zone 30N Euclidean distance via `pyproj`) that this change also needs — but it lives in a Postgres-specific infrastructure module with no SQL dependency of its own.

## Goals / Non-Goals

**Goals:**
- Notify a vehicle's owner, via their preferred channel, when the vehicle moves more than a configurable distance since its previously recorded location.
- Message text is in the user's chosen `notification_language`, and includes the vehicle's plate; a Telegram location pin accompanies it.
- Generalize the existing hardcoded Telegram-link confirmation onto the same localization mechanism, so there's exactly one place notification text gets built for both message kinds.

**Non-Goals:**
- Per-event-type opt-in/opt-out (e.g. "notify me on movement but not on X") — deferred to a later change. If a user has any `preferred_notification_channel` connected, they receive this notification kind unconditionally.
- A general i18n/gettext framework — two message kinds don't justify one.
- Reverse geocoding into a human-readable address — the location pin itself conveys "here."
- Any notification channel besides Telegram (WhatsApp, email, etc.) implementing the new `location` field — `NotificationMessage.location` is channel-agnostic by construction, but only `TelegramNotificationChannel` gets a concrete implementation.
- Rate-limiting or batching beyond the movement threshold itself (e.g. no "at most one notification per hour" cap) — the threshold is the only throttle.

## Decisions

### 1. Movement detection: new `VehicleLocationRepository.get_previous`, not an event-payload change
`VehicleLocationUpdated` stays a plain "this happened" fact — adding "the previous location" to its payload would couple a shared domain event (also consumed by `SerTicketTriggerHandler`) to a need only the notification handler has. Instead, `NotificationDispatchHandler` calls a new `get_previous(vehicle_id, before: datetime) -> VehicleLocation | None`, querying for the row with the greatest `recorded_at` that is still less than the event's `recorded_at` (i.e., excluding the just-saved row). Returns `None` if this is the vehicle's first-ever recorded location — in which case no notification is sent (there's nothing to compare against, and "first ever location" isn't itself a "moved" event).

**Alternative considered**: capture the previous location in `RecordVehicleLocation.execute` (call `get_latest` before `save`) and thread it into the event. Rejected — grows the event's payload for a single subscriber's concern, and `RecordVehicleLocation` would need to reason about "previous location" semantics it otherwise doesn't care about.

### 2. `distance_m` extracted to `domain/value_objects/location.py`, alongside `GeoLocation`
Moved out of `infrastructure/repositories/postgres/ser_zone_repo.py` since it's a pure function (only `math` + `pyproj`, no SQL, no `Engine`) that both `ser_zone_repo.py` and the new notification handler need. Importing a pure geo-math helper from a Postgres-specific infrastructure module into an application-layer handler would be a layering violation; hosting it next to `GeoLocation` in the domain layer is the natural home. `ser_zone_repo.py` updates its import; its behavior and the `ser-zone-query`/`ser-zone-ingestion` capabilities are otherwise unchanged — this is a pure refactor, not a spec change for those capabilities.

### 3. Movement threshold: `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var, default 50
Mirrors this codebase's existing convention for operational tuning knobs (`VEHICLE_POLL_INTERVAL_MINUTES`, `INGESTION_INTERVAL_HOURS`). 50m is a starting default loose enough to absorb ordinary GPS jitter on a parked vehicle while still catching a real move out of a parking spot.

### 4. `NotificationMessage` gains `location: GeoLocation | None`; `NotificationChannelPort.send`'s single-method shape is unchanged
```python
@dataclass(frozen=True)
class NotificationMessage:
    text: str
    location: GeoLocation | None = None
```
`TelegramNotificationChannel.send` branches internally: always calls `sendMessage` for `text`, and additionally calls `sendLocation` when `location` is set. This is two Telegram Bot API HTTP calls per `send()` invocation when both are present — Telegram's `sendLocation` endpoint has no caption parameter, so there is no way to combine them into one call. The port's caller-facing contract stays "one logical notification, one `send()` call," even though the concrete Telegram implementation fans out internally.

**Alternative considered**: a self-hosted static map image (stitched from tile server tiles) attached as an actual photo. Rejected for this change — `sendLocation` ships faster with zero new dependencies and gives a better (interactive, tappable) result in Telegram specifically; revisit only if a channel without a native location-message concept needs supporting later.

### 5. `SendNotification.execute(user_id, text) → execute(user_id, message: NotificationMessage)`
The caller (handler or webhook) now builds the fully-formed, localized `NotificationMessage` before calling `SendNotification`, which stays a pure "look up the preferred channel, deliver this already-built message, fail closed if unset/stale" operation — it does not know about templates, language, or vehicles. Safe to change since nothing calls `SendNotification` in production yet (`NotificationDispatchHandler` was the only intended caller, and it's still inert until this change lands).

### 6. Notification templates: a small per-language string dict, not a framework
```python
# application/notification_templates.py (illustrative — exact shape decided at implementation)
_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "vehicle_moved": "Your car with plate {plate} is now located here.",
        "telegram_linked": "✅ Linked!",
    },
    "es": {
        "vehicle_moved": "Tu coche con matrícula {plate} está ahora aquí.",
        "telegram_linked": "✅ ¡Vinculado!",
    },
}

def render(key: str, language: str | None, **kwargs: str) -> str:
    lang = language if language in _TEMPLATES else "en"
    return _TEMPLATES[lang][key].format(**kwargs)

SUPPORTED_LANGUAGES = frozenset(_TEMPLATES.keys())
```
Both `NotificationDispatchHandler` and the Telegram webhook's link-success path call this same `render()`, using the target user's `notification_language` (defaulting to `"en"` when unset or unrecognized). This is intentionally not a generalized i18n system (no `.po`/`.mo` compilation, no `gettext`) — two message kinds don't justify that infrastructure, consistent with this codebase's existing preference for small, explicit code over frameworks until a real second need appears. `SUPPORTED_LANGUAGES` is exported for `PUT /preferences` to validate against (decision 7) — a single source of truth shared between rendering and validation, rather than two lists that could drift apart.

### 7. `user_preferences.notification_language`: nullable, validated against the supported set (422 if unrecognized)
Mirrors `preferred_notification_channel`'s validation style: `PUT /preferences` rejects a `notification_language` that isn't one of the system's supported languages, the same way it rejects a channel the user hasn't connected. `null` is always accepted (clears the preference, falls back to default at render time).

The supported set is not a third, separately-maintained list — it's `notification_templates._TEMPLATES.keys()` (currently `{"en", "es"}`), the same set the render function already needs to know about. This keeps validation and rendering from silently drifting apart: adding a language means adding one entry to `_TEMPLATES`, and both validation and rendering pick it up automatically. This set is also intended to match the frontend's `i18n.ts` `supportedLngs: ["en", "es"]` — not by any shared-code mechanism (Python and the frontend's TypeScript aren't cross-importable here), but as a convention to keep in sync by hand, the same way the frontend's language dropdown (task 10.2) is populated from a small hardcoded list mirroring `i18n.ts`, not a new catalog endpoint (unlike notification *channels*, where a catalog endpoint was justified by genuinely different connect-flow shapes per channel — languages don't have that problem, they're just a closed, rarely-changing set of codes, the same category `SerProvidersPage`'s `KNOWN_PROVIDERS` already covers by convention).

**Alternative considered (superseded)**: accept any value, falling back silently to the default at render time. Initially chosen on the reasoning that an unrecognized language "isn't an error state the way an unconnected channel is." Reversed per explicit user direction: the user wants a hard 422 for unrecognized values, mirroring `preferred_notification_channel`'s validation exactly, not a silent fallback.

### 8. `NotificationDispatchHandler`'s new dependencies
Constructor grows from `()` to `(vehicle_repo, vehicle_location_repo, user_preferences_repo, send_notification)`, wired in `app.py`'s lifespan setup alongside the other use cases. `handle(event)`:
1. `vehicle = vehicle_repo.get_by_id(event.vehicle_id)` — needed for `license_plate` and `user_id`. If `None` (shouldn't happen under normal operation, but the vehicle could theoretically be deleted between the location write and handler execution — see `vehicle-delete` capability), skip silently; this is defensive, not a documented requirement (no spec scenario needed for an already-guarded-elsewhere edge case).
2. `previous = vehicle_location_repo.get_previous(event.vehicle_id, before=event.recorded_at)`. If `None` (first-ever location), skip.
3. `if distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude) < get_notification_movement_threshold_meters(): return` — no notification.
4. `preferences = user_preferences_repo.find_by_user_id(vehicle.user_id)`; `text = render("vehicle_moved", preferences.notification_language, plate=vehicle.license_plate)`.
5. `send_notification.execute(vehicle.user_id, NotificationMessage(text=text, location=GeoLocation(event.latitude, event.longitude)))`.

## Risks / Trade-offs

- **[Risk] `SendNotification`'s signature change is a breaking API change to the use case.** → Mitigated: no production caller exists yet, so no live behavior is altered from any user's perspective.
- **[Risk] A 50m default threshold is a guess, not measured against real GPS traces.** → Acceptable as a starting point; it's an env var specifically so it can be retuned per deployment without a code change if it proves too noisy or too insensitive.
- **[Trade-off] Movement-only dedup means a vehicle bouncing right at the threshold boundary (e.g. GPS drift oscillating around 50m) could still notify repeatedly.** → Accepted for this change; a hysteresis/cooldown mechanism (e.g. "at most one notification per N minutes regardless of movement") is a reasonable follow-up if this proves annoying in practice, but is speculative to build now without evidence it's needed.
- **[Trade-off] `sendLocation` is Telegram-specific; a future non-Telegram channel needs its own answer for "show where the car is."** → Accepted, per decision 4 — `NotificationMessage.location` stays channel-agnostic in shape even though only one channel implementation exists.

## Migration Plan

1. Add Alembic migration adding `notification_language TEXT NULL` to `user_preferences`.
2. Add `VehicleLocationRepository.get_previous` to the port and its Postgres implementation.
3. Extract `distance_m` to `domain/value_objects/location.py`; update `ser_zone_repo.py`'s import.
4. Deploy backend: `NotificationMessage`/`SendNotification`/`TelegramNotificationChannel` changes, notification-templates module, real `NotificationDispatchHandler`, `user_preferences` API/schema changes, new env var.
5. Deploy frontend: notification-language selector on the Preferences page.
6. Rollback: revert code; drop the added column. No data loss beyond the new preference itself (no prior production users, since it doesn't exist yet). No irreversible external side effects — worst case during a bad rollout is either missed or spurious location notifications, not data corruption.

## Open Questions

None outstanding — resolved during exploration (see prior `/opsx:explore` session): movement-threshold dedup mechanism (new repo method, env-var threshold), map mechanism (Telegram `sendLocation`, not a stitched image), `distance_m` extraction, and `SendNotification`'s signature change were all decided there.
