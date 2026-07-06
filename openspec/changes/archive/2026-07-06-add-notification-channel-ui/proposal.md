## Why

The `add-telegram-notification-channel` change shipped a fully working backend (link-code generation, webhook-based linking, list/delete of configured channels) but deliberately left the frontend out of scope — connecting Telegram today requires manually calling `POST /notifications/telegram/link-code` and following the deep link by hand. It also deferred channel *preference*, since only one channel type existed. This change closes both gaps: it gives users a UI to connect/disconnect notification channels, and introduces a preferred-channel preference now that the machinery to have more than one channel is in place — without deciding *when* an actual notification fires, which stays a no-op (`NotificationDispatchHandler`) and is explicitly deferred to a subsequent change.

## What Changes

- Add `GET /notifications/available-channels` (authenticated), returning the system's registered channel ids (currently `["telegram"]`) sourced from `app.state.notification_channels` — not hardcoded on the frontend, unlike the existing SER-provider convention.
- Add `preferred_notification_channel: str | None` to `user_preferences` (new column + migration), alongside `default_ticket_duration_minutes` and `auto_create_ticket`.
- `SendNotification` now sends only to the user's `preferred_notification_channel` if it is set and currently connected; it is a no-op (fail closed, no fallback fan-out) if the preferred channel is unset or no longer connected. This **replaces** its current "send to every configured channel" behavior. **BREAKING** (internal use case contract change; no external API caller depends on the old fan-out behavior since nothing calls `SendNotification` in production yet).
- Connecting a user's first notification channel auto-sets it as `preferred_notification_channel` if no preference is set yet.
- Disconnecting a channel that is the user's current `preferred_notification_channel` clears the preference back to `None`.
- Add a "Notification Channels" page: lists available channels (from the catalog endpoint) against the user's configured channels, with per-channel connect/disconnect actions, mirroring `SerProvidersPage`'s list/connect-modal/disconnect shape.
- Add a Telegram-specific connect flow component: requests a link-code, displays the deep link, and polls `GET /notifications/channels` (bounded, while the connect UI is open) until the channel appears as configured.
- Add a "preferred notification channel" selector to the existing Preferences page, populated from the user's currently connected channels.
- Frontend channel-id → connect-flow-component mapping is a small local registry (necessarily channel-specific code), but *which channels exist* is no longer hardcoded — it comes from the new catalog endpoint.

## Capabilities

### New Capabilities
(none — this extends existing capabilities rather than introducing a new domain concept)

### Modified Capabilities
- `notification-channel`: adds the available-channels catalog endpoint; changes `SendNotification` from fan-out-to-all to preferred-channel-only with fail-closed behavior; adds auto-select-on-first-connect and clear-on-disconnect side effects.
- `user-preferences`: adds the `preferred_notification_channel` field, its persistence, and its API exposure.

## Impact

- **Backend**: `user_preferences` table/migration, `UserPreferences` entity, preferences repository, preferences API schema; `SendNotification`, `RemoveNotificationChannel`, and the Telegram webhook handler (or a shared connect-completion path) gain preferred-channel side effects; new `available-channels` route on the notifications router.
- **Frontend**: new Notification Channels page, Telegram connect-flow component, channel-id → component registry, extended Preferences page and its API client, new API client calls for the catalog endpoint.
- **No changes** to `NotificationDispatchHandler` (stays a no-op) or to any real notification-triggering logic — that remains out of scope for this change.
