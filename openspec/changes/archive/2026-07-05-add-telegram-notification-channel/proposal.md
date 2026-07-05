## Why

`user_preferences.auto_create_ticket` has had a `False` branch with nothing behind it since it was introduced — "notify the user instead" has never had a channel to notify through. This change builds that channel: a generic, channel-agnostic notification interface plus its first concrete implementation (Telegram, chosen over WhatsApp for this first pass since it requires no business verification, no message-template pre-approval, and no per-message cost — see design.md for the full comparison).

## What Changes

- Add `NotificationChannelPort` with a single abstract method, `send(recipient, message) -> None`, deliberately channel-agnostic so a future WhatsApp implementation can be added without touching this port.
- Add per-user, per-channel config storage (`user_notification_channel_configs`) — unlike SER provider sessions, this isn't encrypted, since a Telegram `chat_id` is an identifier, not a credential.
- Add `TelegramNotificationChannel`, implementing `send()` via the Telegram Bot API.
- Add the Telegram account-linking flow: an authenticated endpoint that issues a signed, time-limited linking token (reusing the `itsdangerous` pattern already used for OAuth CSRF state), and a webhook endpoint that receives the user's `/start <token>` message, verifies it, and stores their `chat_id`. The linking confirmation message doubles as the live proof that `send()` works.
- Add a minimal `SendNotification` use case: sends to whatever channel(s) a user has configured. No preference logic yet — with only one possible channel, there's nothing to choose between.
- Add a no-op event-handler stub (mirroring `SerTicketTriggerHandler`'s exact pattern), subscribed to `VehicleLocationUpdated`, proving the event-to-notification wiring shape exists without yet deciding when a real notification should fire.
- Add `GET /notifications/channels` (list a user's configured channels) and `DELETE /notifications/channels/{channel}` (remove one), mirroring the SER provider connections' list/delete shape. Unlike SER provider disconnect, there's no server-side "logout" to attempt first — Telegram has no revocation concept for a bot to call; deleting the local config is the entire operation.

## Capabilities

### New Capabilities
- `notification-channel`: the port, Telegram implementation, per-user config storage, linking flow, minimal send use case, and the no-op event-wiring stub.

### Modified Capabilities
(none — the new event-handler stub is an additive subscriber to the existing `VehicleLocationUpdated` event; publishing behavior in `vehicle-location-events` doesn't change)

## Impact

- **Backend**: new port/entity/value-object files, new Postgres repository + migration, new Telegram infrastructure adapter, four new endpoints, new use cases, new event handler.
- **API surface**: `POST /notifications/telegram/link-code` (protected), `POST /notifications/telegram/webhook` (public, validated via Telegram's webhook secret token), `GET /notifications/channels` (protected), `DELETE /notifications/channels/{channel}` (protected).
- **No frontend changes** in this proposal — there's no "Connect Telegram" button yet; the linking flow is reachable via the API directly (curl / a real Telegram bot) for now. A follow-up change adds the UI plus channel-preference management, mirroring how the SER provider UI followed its raw provider implementation.
- **External dependency**: requires creating a real Telegram bot (via @BotFather) and registering a webhook URL with Telegram — a one-time, free, self-serve setup step, no approval process.
