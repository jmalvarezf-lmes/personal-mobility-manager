## Context

`user_preferences.auto_create_ticket` has a `False` branch that's never had anywhere to go — the intent was always "notify the user instead of creating a ticket automatically," but no notification mechanism exists. `SerTicketTriggerHandler` (a no-op subscriber to `VehicleLocationUpdated`) is where that decision will eventually live, but this change doesn't touch it — it only builds the notification channel itself, mirroring how `add-ser-ticket-provider-interface` built the SER provider abstraction well before any real trigger logic existed for it.

### Telegram vs. WhatsApp — why Telegram first

|  | One-time setup | Per-user linking |
|---|---|---|
| **Telegram** | Trivial — message @BotFather, get a token, self-serve, free, no review | **Mandatory** — a bot can only message users who have already started a conversation with it; there is no way to push to an arbitrary Telegram account |
| **WhatsApp Business API** | Real friction — Meta Business account, phone verification, business verification (can take days), template message pre-approval for anything outside a 24h customer-initiated window | **None needed**, if a phone number is already collected — template messages can be pushed to any number without an inbound step |

WhatsApp has materially better penetration in Spain, but its one-time setup cost (business verification, template approval, an external dependency on Meta's review timeline) doesn't fit this project's pace of shipping. Telegram's mandatory per-user linking flow is real ongoing complexity, but it's fully self-contained and buildable today. `NotificationChannelPort` is designed channel-agnostic specifically so WhatsApp can be added later without revisiting this port.

## Goals / Non-Goals

**Goals:**
- `NotificationChannelPort.send(recipient, message) -> None` — a channel-agnostic interface, not tied to any Telegram-specific concept.
- `TelegramNotificationChannel` — a working, real implementation (not a stub), since this is the first concrete channel and needs to be provably functional.
- A per-user linking flow that proves `send()` works against the live Telegram API, without a separate manual test endpoint.
- A minimal `SendNotification` use case and a no-op event-handler stub, proving the wiring shape without deciding any real trigger logic yet.

**Non-Goals:**
- Any frontend UI — no "Connect Telegram" button. The linking endpoints are reachable directly (curl, or via a real Telegram client interacting with the bot) — a follow-up change adds the UI.
- Channel *preference* — with only one possible channel, there's nothing to prefer between yet. `SendNotification` sends to whatever's configured, full stop.
- Real trigger logic — deciding *when* to notify about *what* is explicitly deferred ("notification by notification," per the proposal). The event-handler stub added here stays a no-op, exactly like `SerTicketTriggerHandler` did in its first change.
- WhatsApp implementation — the port is designed to allow it later, but it isn't built here.

## Decisions

### 1. `NotificationChannelPort` — single abstract method, opaque recipient/message value objects
```python
@dataclass(frozen=True)
class NotificationRecipient:
    data: dict[str, Any]   # e.g. {"chat_id": 123456789} for Telegram

@dataclass(frozen=True)
class NotificationMessage:
    text: str

class NotificationChannelPort(ABC):
    def send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None: ...
```
Mirrors `SerProviderCredentials`/`SerProviderSession`'s wrapper convention: a named value object crosses the port boundary, but its contents stay channel-defined. `NotificationMessage` is deliberately just `text: str` — both Telegram and (eventually) WhatsApp support plain text messages, and richer message types (buttons, images) can be added if a real future need appears, not speculatively now.

### 2. Linking is NOT part of the abstract port
Unlike `SerTicketProviderPort.login()` (shared across all SER providers), Telegram's linking mechanism is a Telegram-platform-specific requirement, not a generalizable "notification channel" concept. WhatsApp, if added later, might need no linking flow at all (just a phone number field). So the linking flow — link-code generation, the webhook, chat_id association — lives as Telegram-specific application/infrastructure code, with no abstract counterpart on the port. A future WhatsApp implementation would define its own connection story entirely, not implement a shared "connect" method.

### 3. Per-user config storage: unencrypted
`user_notification_channel_configs` (`user_id`, `channel`, `config` as plain JSON — not Fernet-encrypted, unlike `vehicle_configs`/`user_ser_provider_configs`). A Telegram `chat_id` is an identifier, not a credential — leaking it doesn't grant access to anything, unlike ElParking's `access_token`. Skipping encryption avoids requiring `ENCRYPTION_KEY` for a table that doesn't need confidentiality, and keeps the repository simpler (no dependency on `infrastructure/crypto.py`).

### 4. Linking flow reuses the existing `itsdangerous` CSRF-state pattern
```
POST /notifications/telegram/link-code   (authenticated)
    → itsdangerous.URLSafeTimedSerializer(JWT_SECRET, salt="telegram-link").dumps({"user_id": ...})
    → returns a deep link: https://t.me/<bot_username>?start=<signed-token>

User clicks the link → Telegram sends "/start <signed-token>" to the bot

POST /notifications/telegram/webhook   (Telegram → us; public, but validated)
    → verify X-Telegram-Bot-Api-Secret-Token header matches TELEGRAM_WEBHOOK_SECRET
    → extract the token from the "/start <token>" message text
    → verify + decode via the same serializer (max_age enforced — matches csrf.py's _STATE_MAX_AGE pattern)
    → extract user_id, store the incoming message's chat.id for (user_id, "telegram")
    → call NotificationChannelPort.send() to reply "✅ Linked!" — this is the live proof send() works
```
Chosen over inventing a new "pending link codes" database table: `itsdangerous` already provides exactly this primitive (signed, time-limited, tamper-proof tokens) and is already a dependency used for the OAuth state parameter (`csrf.py`). A different `salt` value domain-separates this token from the OAuth state token and the session JWT, so a token generated for one purpose can't be replayed as another — same technique already established in this codebase. No new table, no expiry cleanup job needed.

The `/start <payload>` mechanism is Telegram's own standard deep-linking convention (not a workaround) — this is the idiomatic way Telegram bots handle "link this chat to an external account."

### 5. Webhook security: validate Telegram's secret token header
Telegram's `setWebhook` API accepts an optional `secret_token`, which Telegram then includes as `X-Telegram-Bot-Api-Secret-Token` on every webhook POST. The webhook handler validates this header against a configured `TELEGRAM_WEBHOOK_SECRET` before processing anything, rejecting requests that don't match. Without this, anyone who discovers the webhook URL could POST arbitrary fake "incoming messages." (The linking token itself is also signed and single-purpose, which limits the damage even without this check, but validating the header is free and standard practice — no reason to skip it.)

### 6. `SendNotification` — minimal, no preference logic
```python
class SendNotification:
    def execute(self, user_id: UUID, text: str) -> bool:
        # looks up whatever channel config(s) exist for user_id, sends via each
        # returns True if at least one send succeeded, False if nothing configured
```
No channel-preference concept yet — deferred to the follow-up change once a second channel type could plausibly exist. For now "whatever's configured" and "the only possible channel" are the same thing.

### 7. No-op event-handler stub, same shape as `SerTicketTriggerHandler`
A new handler (name TBD at task-breakdown time, e.g. `NotificationDispatchHandler`), subscribed to `VehicleLocationUpdated` at startup, with a no-op `handle()` body — proving the DI wiring compiles and the subscription exists, without deciding any real trigger condition. Exactly the same "widen little by little" discipline already used twice in this codebase.

### 8. List and delete — simpler than the SER provider precedent, no server-side revocation
`GET /notifications/channels` returns the list of channels a user has configured (mirrors `GET /ser-ticket-providers/connections`'s collection shape). `DELETE /notifications/channels/{channel}` removes one.

Unlike SER provider disconnect (`DisconnectSerTicketProvider`, which attempts a best-effort `provider.logout()` before deleting locally), there's no equivalent server-side step here: Telegram has no API for a bot to revoke or invalidate a chat_id — the bot simply stops being able to usefully message that chat if the user blocks it, but there's nothing for *us* to call. So deletion is a single, unconditional step: `UserNotificationChannelConfigRepository.delete(user_id, channel)`, idempotent (no error if nothing was configured). No `logout_succeeded`-style boolean is needed in the response — `DELETE` can simply return `204 No Content`.

## Risks / Trade-offs

- **[Risk] No frontend means the linking flow is only exercised via curl/a real bot during development.** → Acceptable — this mirrors exactly how ElParking's connect endpoint shipped and was manually verified before any UI existed.
- **[Risk] Telegram requires the user to have a Telegram account at all — real coverage gap for users who don't.** → Accepted trade-off, per the explicit decision to prioritize build speed over WhatsApp's better penetration for this first channel; the port is designed so WhatsApp isn't precluded later.
- **[Trade-off] Storing `chat_id` unencrypted is a deliberate departure from every other provider-config table in this codebase.** → Justified specifically because `chat_id` isn't a credential; if a future channel's config *does* need confidentiality (e.g. a channel requiring stored API keys), that channel's config storage should encrypt, independently of this decision.

## Migration Plan

1. Add Alembic migration for `user_notification_channel_configs`.
2. Create a real Telegram bot via @BotFather (manual, one-time, outside this codebase) to obtain a bot token.
3. Deploy backend changes; register the webhook URL with Telegram (`setWebhook`, one-time call, likely a small operational script or manual `curl` — not part of the application's runtime code).
4. No frontend deploy needed — nothing references this from the UI yet.
5. Rollback: revert the code change; drop the migration; no data loss beyond what was never populated in production use.

## Open Questions

None outstanding.
