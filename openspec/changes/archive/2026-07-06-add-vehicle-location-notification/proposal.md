## Why

`NotificationDispatchHandler` has been a deliberate no-op scaffold since `add-telegram-notification-channel`, and the connect/preference machinery from `add-notification-channel-ui` gave users a way to pick a channel with nothing yet using it. This change activates the first real notification: when a vehicle moves meaningfully, the owner gets a message with the vehicle's plate and a map pin of its new location, in their preferred language. Per-event-type configurability (letting users opt in/out of specific notification kinds) is explicitly deferred to a later change — for now, having any preferred channel connected means receiving this one notification kind, unconditionally.

## What Changes

- Activate `NotificationDispatchHandler`: on `VehicleLocationUpdated`, look up the vehicle (plate, owner), compute the distance moved since the previous recorded location, and — only if it exceeds a configurable threshold — send a localized notification with the plate and a Telegram native location pin.
- Add `VehicleLocationRepository.get_previous(vehicle_id, before: datetime) -> VehicleLocation | None`, since the event fires after the new location is already saved, so `get_latest` can't be used to find the prior point.
- Add `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var (default 50) controlling the minimum movement distance that triggers a notification.
- Extract the existing `distance_m(lat1, lng1, lat2, lng2)` helper out of `infrastructure/repositories/postgres/ser_zone_repo.py` into a shared, layer-appropriate location (alongside `GeoLocation` in `domain/value_objects/location.py`), since it's a pure function with no SQL/repo dependency and the new notification handler needs it too. `ser_zone_repo.py` imports it from its new home; its behavior is unchanged. This is a pure refactor — no spec-level requirement changes to the `ser-zone-query`/`ser-zone-ingestion` capabilities.
- Add `user_preferences.notification_language` (nullable, e.g. `"en"`/`"es"`), defaulting to `"en"` at use-site when unset. `PUT /preferences` rejects (422) any non-null value that isn't one of the system's supported languages, mirroring `preferred_notification_channel`'s validation — the same set the frontend's `i18n.ts` already exposes as `supportedLngs`.
- Add a small hand-rolled notification-template mechanism (a per-language string dict, not a general i18n framework — only two message kinds exist) covering: the vehicle-moved message and the existing Telegram-link confirmation.
- `NotificationMessage` gains an optional `location: GeoLocation | None` field (alongside the existing `text: str`).
- `SendNotification.execute(user_id, text)` **BREAKING** → `SendNotification.execute(user_id, message: NotificationMessage)` — callers now build the fully-localized message themselves before handing it off; `SendNotification` stays a pure "deliver to the preferred channel" operation. Safe to change since nothing calls it in production yet.
- `TelegramNotificationChannel.send` gains a second Telegram Bot API call (`sendLocation`) when `message.location` is set — Telegram's `sendLocation` has no caption field, so a message with both text and a location results in two separate Telegram API calls (`sendMessage` then `sendLocation`), not one combined call.
- The Telegram webhook's link-confirmation message moves off its hardcoded English string onto the new template mechanism, using the linking user's `notification_language`.

## Capabilities

### New Capabilities
- `vehicle-location-notification`: the movement-threshold trigger logic that turns `VehicleLocationUpdated` into an actual notification — vehicle/owner lookup, distance-since-previous computation, threshold gating, and message construction.

### Modified Capabilities
- `notification-channel`: `NotificationMessage` gains `location`; `SendNotification`'s signature changes to accept a `NotificationMessage`; `TelegramNotificationChannel` gains `sendLocation` support; the Telegram link-confirmation becomes localized via the new template mechanism.
- `user-preferences`: adds `notification_language`, its persistence, and its API exposure (read/update), mirroring how `preferred_notification_channel` was added.
- `vehicle-location-query`: `VehicleLocationRepository` gains `get_previous(vehicle_id, before) -> VehicleLocation | None`.

## Impact

- **Backend**: `VehicleLocationRepository` port + Postgres implementation, `NotificationDispatchHandler` (now real), a new notification-templates module, `NotificationMessage`/`SendNotification`/`TelegramNotificationChannel` changes, `user_preferences` migration/entity/repo/API changes, `distance_m` extraction (touches `ser_zone_repo.py`'s import, no behavior change), new env var and its `config.py` accessor, DI wiring in `app.py`.
- **Frontend**: a "notification language" selector on the Preferences page, alongside the existing preferred-channel selector.
- **No changes** to event-type configurability (still deferred), to `SerTicketTriggerHandler` (still inert), or to any other notification channel besides Telegram.
