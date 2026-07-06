## 1. distance_m extraction (pure refactor)

- [x] 1.1 Move `distance_m(lat1, lng1, lat2, lng2)` from `infrastructure/repositories/postgres/ser_zone_repo.py` into `domain/value_objects/location.py` (alongside `GeoLocation`)
- [x] 1.2 Update `ser_zone_repo.py` to import `distance_m` from its new location; remove the old definition
- [x] 1.3 Run existing SER-zone tests to confirm no behavior change (`tests/infrastructure/test_ser_zone_repo_integration.py` or equivalent — find the actual test file covering `find_nearest`)

## 2. VehicleLocationRepository.get_previous

- [x] 2.1 Add `get_previous(vehicle_id: UUID, before: datetime) -> VehicleLocation | None` to the `VehicleLocationRepository` port (`domain/ports/vehicle_location_repository.py`)
- [x] 2.2 Implement in `infrastructure/repositories/postgres/vehicle_location_repo.py`: query the row with the greatest `recorded_at` strictly less than `before` for the given `vehicle_id`
- [x] 2.3 Extend `tests/infrastructure/test_vehicle_location_repo_integration.py` covering: returns the second-most-recent row, returns `None` when `before` is the vehicle's only recorded location

## 3. Movement threshold config

- [x] 3.1 Add `get_notification_movement_threshold_meters() -> float` to `config.py`, reading `NOTIFICATION_MOVEMENT_THRESHOLD_METERS`, defaulting to `50` (mirror `get_vehicle_poll_interval_minutes`'s int-parsing-with-fallback pattern)
- [x] 3.2 Add `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` to `.env.example` with a short comment

## 4. NotificationMessage gains an optional location

- [x] 4.1 Add `location: GeoLocation | None = None` to `domain/value_objects/notification_message.py`, update its module docstring (the "richer message types... not speculatively now" comment no longer applies)
- [x] 4.2 Update `TelegramNotificationChannel.send` (`infrastructure/notification_channels/telegram/channel.py`) to additionally call Telegram's `sendLocation` endpoint (same `chat_id`, `latitude`/`longitude` from `message.location`) when `message.location` is set — a separate HTTP call from `sendMessage`, since `sendLocation` has no caption parameter
- [x] 4.3 Extend `tests/infrastructure/test_telegram_notification_channel.py`: sending a message with `location` set triggers both a `sendMessage` and a `sendLocation` call; sending without `location` triggers only `sendMessage`

## 5. Notification templates

- [x] 5.1 Add a small templates module (e.g. `application/notification_templates.py`) with a per-language string dict covering `"vehicle_moved"` (with a `{plate}` placeholder) and `"telegram_linked"`, at least `"en"` and `"es"`, a `render(key, language, **kwargs) -> str` function that falls back to `"en"` for `None`/unrecognized languages, and an exported `SUPPORTED_LANGUAGES = frozenset(_TEMPLATES.keys())` for the preferences validation in section 8 to reuse
- [x] 5.2 Add unit tests for `render`: known kind + supported language renders correctly with substitution; `None` language falls back to default; unrecognized language code falls back to default

## 6. SendNotification: accept a NotificationMessage

- [x] 6.1 Change `SendNotification.execute(user_id: UUID, text: str) -> bool` to `execute(user_id: UUID, message: NotificationMessage) -> bool` (`application/use_cases/send_notification.py`) — no other behavior change (still preferred-channel-only, fail-closed)
- [x] 6.2 Update `tests/application/use_cases/test_send_notification.py` for the new signature (construct a `NotificationMessage` in each test instead of passing a raw string)

## 7. Telegram webhook: localized link confirmation

- [x] 7.1 In `presentation/api/routers/notifications.py`'s webhook handler, replace the hardcoded `_LINK_CONFIRMATION_TEXT` with a call to the new `render("telegram_linked", language, ...)`, where `language` comes from `request.app.state.user_preferences_repo.find_by_user_id(user_id).notification_language`
- [x] 7.2 Update `tests/presentation/test_notifications_router.py` to cover: confirmation text is localized when `notification_language` is set; falls back to default when unset

## 8. user_preferences: notification_language field

- [x] 8.1 Add Alembic migration adding `notification_language TEXT NULL` to `user_preferences` (chained after the most recent `user_preferences` migration — check `alembic heads` for the current head first)
- [x] 8.2 Add `notification_language: str | None` to `UserPreferences` entity (`domain/entities/user_preferences.py`)
- [x] 8.3 Update `UserPreferencesRepository` port: `update(...)` gains `notification_language: str | None` (`domain/ports/user_preferences_repository.py`)
- [x] 8.4 Implement in `infrastructure/repositories/postgres/user_preferences_repo.py` and `infrastructure/orm/tables.py`
- [x] 8.5 Update `UserPreferencesResponse` / `UpdateUserPreferencesRequest` schemas (`presentation/api/schemas.py`) to include `notification_language: str | None`
- [x] 8.6 Update `GET`/`PUT /preferences` handlers (`presentation/api/routers/preferences.py`): `PUT` validates a non-null `notification_language` against `notification_templates.SUPPORTED_LANGUAGES`, returning `422` if not recognized — same style as the existing `preferred_notification_channel` check; `null` is always accepted
- [x] 8.7 Extend `tests/infrastructure/test_user_preferences_repo_integration.py` and `tests/presentation/test_preferences_api.py` for the new field, including "unrecognized language rejected with 422" and "null clears the preference" scenarios

## 9. NotificationDispatchHandler: real implementation

- [x] 9.1 Rewrite `application/event_handlers/notification_dispatch_handler.py`: constructor takes `vehicle_repo`, `vehicle_location_repo`, `user_preferences_repo`, `send_notification`; `handle(event)` implements the lookup → previous-location → threshold → render → `SendNotification.execute` flow described in design.md decision 8
- [x] 9.2 Reorder `presentation/api/app.py`'s lifespan wiring: move the `--- Notification channels ---` block (building `send_notification_uc` and friends) to right after the `--- Auth (Users) ---` block, and move the `--- Events ---` block (constructing `NotificationDispatchHandler` with its new dependencies and subscribing it) to after both the `--- Vehicles ---` block and the (now-earlier) `--- Notification channels ---` block — `NotificationDispatchHandler` now needs `vehicle_repo`, `vehicle_location_repo`, `user_preferences_repo`, and `send_notification_uc`, all of which must already exist at construction time
- [x] 9.3 Rewrite `tests/application/event_handlers/test_notification_dispatch_handler.py` covering all scenarios in the `vehicle-location-notification` spec: movement past threshold notifies, movement below threshold doesn't, first-ever location doesn't, missing vehicle is skipped without error, message is localized, falls back to default language

## 10. Frontend: notification language preference

- [x] 10.1 Update `frontend/src/api/preferences.ts` types for `notification_language: string | null`
- [x] 10.2 Update `frontend/src/pages/PreferencesPage.tsx`: add a language selector (supported languages hardcoded client-side — this is a genuinely small, slow-changing enumeration, consistent with the `SerProvidersPage` convention, unlike notification *channels* which intentionally broke from it), wired into the existing `handleSubmit`
- [x] 10.3 Add i18n keys for the new control
- [x] 10.4 Update `frontend/e2e/preferences.spec.ts` / `frontend/e2e/pages/PreferencesPage.ts` mocks to include `notification_language` in the preferences fixture, and add a scenario covering picking a language
