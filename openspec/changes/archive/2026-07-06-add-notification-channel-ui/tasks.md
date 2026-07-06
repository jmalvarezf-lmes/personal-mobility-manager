## 1. Migration and domain entity

- [x] 1.1 Add Alembic migration adding `preferred_notification_channel TEXT NULL` to `user_preferences` (revision chained after `k8l9m0n1o2p3_create_user_notification_channel_configs`)
- [x] 1.2 Add `preferred_notification_channel: str | None` to the `UserPreferences` entity (`domain/entities/user_preferences.py`)

## 2. Preferences repository

- [x] 2.1 Update `UserPreferencesRepository` port: `update(...)` gains `preferred_notification_channel: str | None`; add new `set_preferred_notification_channel(user_id: UUID, channel: str | None) -> None`
- [x] 2.2 Implement both in `infrastructure/repositories/postgres/user_preferences_repo.py`
- [x] 2.3 Update/extend integration tests in `tests/infrastructure/test_user_preferences_repo_integration.py` for the new field and the new method (including clearing via `None`)

## 3. Notification-channel side effects (auto-select / clear-on-disconnect)

- [x] 3.1 In the Telegram webhook handler's successful-link path (`presentation/api/routers/notifications.py`), after `config_repo.save(...)`, call `user_preferences_repo.find_by_user_id` and, if `preferred_notification_channel` is `None`, call `set_preferred_notification_channel(user_id, "telegram")`
- [x] 3.2 Update `RemoveNotificationChannel.execute` (`application/use_cases/remove_notification_channel.py`) to accept the preferences repo, check whether `channel` equals the user's current `preferred_notification_channel`, and clear it via `set_preferred_notification_channel(user_id, None)` if so, in the same call
- [x] 3.3 Update `SendNotification.execute` (`application/use_cases/send_notification.py`) to look up `preferred_notification_channel` via the preferences repo and send only to that channel if connected; return `False` without sending if unset or stale (no fan-out fallback)
- [x] 3.4 Update unit tests for `SendNotification` and `RemoveNotificationChannel` to cover: preferred+connected sends succeed, unset preference returns `False`, stale preference returns `False` with no fallback, disconnecting the preferred channel clears the preference, disconnecting a non-preferred channel leaves it untouched

## 4. Available-channels endpoint

- [x] 4.1 Add `GET /notifications/available-channels` to `presentation/api/routers/notifications.py`, requiring auth, returning `{"channels": list(request.app.state.notification_channels.keys())}`
- [x] 4.2 Add a schema (or reuse `NotificationChannelsResponse`) for the response shape
- [x] 4.3 Add a route test covering authenticated success and anonymous 401

## 5. Preferences API and validation

- [x] 5.1 Update `UserPreferencesResponse` and `UpdateUserPreferencesRequest` schemas to include `preferred_notification_channel: str | None`
- [x] 5.2 Update `GET /preferences` and `PUT /preferences` handlers (`presentation/api/routers/preferences.py`) to read/write the new field
- [x] 5.3 In `PUT /preferences`, validate that a non-null `preferred_notification_channel` corresponds to a channel the current user has configured (via `UserNotificationChannelConfigRepository.find`); return `422` if not
- [x] 5.4 Update `tests/presentation/test_preferences_api.py` for the new field, including the "unconfigured channel rejected" and "clear via null" scenarios

## 6. Frontend: notification channels API client

- [x] 6.1 Add `frontend/src/api/notifications.ts` with `getAvailableChannels()`, `getConfiguredChannels()`, `disconnectChannel(channel)`, `createTelegramLinkCode()`
- [x] 6.2 Update `frontend/src/api/preferences.ts` types for `preferred_notification_channel`

## 7. Frontend: Notification Channels page

- [x] 7.1 Add `frontend/src/pages/NotificationChannelsPage.tsx`: fetch available + configured channels, render one row per available channel (connected/not-connected state), mirroring `SerProvidersPage`'s structure
- [x] 7.2 Add a small channel-id → connect-flow-component registry (e.g. `frontend/src/components/notificationChannels/registry.ts`), with `"telegram"` mapped to the component from 7.3; unrecognized ids render a disabled/"not yet supported" row
- [x] 7.3 Add `frontend/src/components/notificationChannels/TelegramConnectFlow.tsx`: calls `createTelegramLinkCode()`, displays the deep link, polls `getConfiguredChannels()` on a bounded interval until `"telegram"` appears or a timeout is reached, with cleanup on unmount
- [x] 7.4 Add a disconnect action per connected channel row, calling `disconnectChannel(channel)` with optimistic UI removal (mirrors `SerProviderRow`)
- [x] 7.5 Register the route (`/notification-channels`) in `App.tsx` as a protected route, and add a nav entry in `Nav.tsx`'s account dropdown
- [x] 7.6 Add i18n keys for the new page (title, loading/error states, connect/disconnect labels, per-channel display names)

## 8. Frontend: Preferences page

- [x] 8.1 Update `PreferencesPage.tsx` to fetch the user's configured channels and render a "preferred notification channel" select populated only from connected channels, plus a "none" option to clear
- [x] 8.2 Wire the select's value into the existing `handleSubmit`'s `updatePreferences` call
- [x] 8.3 Add i18n keys for the new control and its empty/no-channels-connected state

## 9. E2E coverage

- [x] 9.1 Extend or add an e2e spec covering: connect Telegram from the UI (using a stubbed/mocked webhook completion), see it listed as connected, pick it as preferred in Preferences, disconnect it, and confirm the preferred-channel preference clears
