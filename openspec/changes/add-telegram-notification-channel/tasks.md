## 1. Domain layer

- [x] 1.1 `domain/value_objects/notification_recipient.py` and `domain/value_objects/notification_message.py` — frozen dataclasses `NotificationRecipient` (`data: dict[str, Any]`) and `NotificationMessage` (`text: str`), mirroring `SerProviderCredentials`/`SerProviderSession`'s docstring/style conventions
- [x] 1.2 `domain/ports/notification_channel.py` — abstract `NotificationChannelPort` with `send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None`. No linking/connection method on this port — see design.md decision 2.
- [x] 1.3 `domain/ports/user_notification_channel_config_repository.py` — abstract `UserNotificationChannelConfigRepository` with `save(user_id: UUID, channel: str, recipient: NotificationRecipient) -> None`, `find(user_id: UUID, channel: str) -> NotificationRecipient | None`, `find_all_by_user_id(user_id: UUID) -> list[tuple[str, NotificationRecipient]]`, `delete(user_id: UUID, channel: str) -> None` (idempotent — no error if nothing to delete)
- [x] 1.4 Add `NotificationChannelApiError` to `domain/exceptions.py` (raised by `TelegramNotificationChannel.send` on failure), following the existing `class XError(Exception): pass` style

## 2. Database migration

- [x] 2.1 Alembic migration: `user_notification_channel_configs` table — `user_id UUID NOT NULL REFERENCES users(id)`, `channel TEXT NOT NULL`, `config TEXT NOT NULL` (JSON, cleartext — no encryption, see design.md decision 3), `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`, composite PK `(user_id, channel)`. Run `alembic heads` first to confirm the correct `down_revision`.
- [x] 2.2 Add `user_notification_channel_configs_table` to `infrastructure/orm/tables.py`

## 3. Infrastructure layer — Telegram channel

- [x] 3.1 `infrastructure/notification_channels/telegram/__init__.py` and `infrastructure/notification_channels/telegram/channel.py` — `TelegramNotificationChannel` implementing `NotificationChannelPort`:
  - `send(recipient, message)`: extract `chat_id` from `recipient.data`, POST to `https://api.telegram.org/bot{token}/sendMessage` with `{"chat_id": ..., "text": message.text}`, using a synchronous `httpx.Client` (mirror `ElParkingSerTicketProvider`'s sync-client style)
  - Wrap `httpx.HTTPError`/non-2xx responses as `NotificationChannelApiError` — no raw `httpx` exception should escape
- [x] 3.2 Add `get_telegram_bot_token() -> str` (required, no default — mirrors `get_elparking_base_url()`'s pattern, raises `RuntimeError` if `TELEGRAM_BOT_TOKEN` is unset) and `get_telegram_webhook_secret() -> str` (same pattern, `TELEGRAM_WEBHOOK_SECRET`) and `get_telegram_bot_username() -> str` (same pattern, `TELEGRAM_BOT_USERNAME`, needed to build the `t.me` deep link) to `config.py`
- [x] 3.3 `infrastructure/repositories/postgres/user_notification_channel_config_repo.py` — `PostgresUserNotificationChannelConfigRepository` implementing the port: `save` JSON-serializes `recipient.data` in cleartext (no Fernet — deliberately, per design.md decision 3) and upserts by `(user_id, channel)`; `find` deserializes, returns `None` if absent; `find_all_by_user_id` returns all rows for a user as `(channel, NotificationRecipient)` tuples; `delete` removes the row for `(user_id, channel)`, no error if absent

## 4. Application layer

- [x] 4.1 `application/use_cases/send_notification.py` — `SendNotification`: `execute(user_id: UUID, text: str) -> bool`. Calls `config_repo.find_all_by_user_id(user_id)`; for each `(channel, recipient)`, resolve the channel instance from an injected `channels: dict[str, NotificationChannelPort]` and call `.send(recipient, NotificationMessage(text=text))`. Returns `True` if at least one send was attempted successfully, `False` if no channels are configured for the user. Decide during implementation whether a single channel's send failure should raise, be swallowed, or be tracked per-channel — keep it simple (raising is fine, since there's no soft-fail requirement here unlike SER provider disconnect) but document the choice.
- [x] 4.2 `application/use_cases/generate_telegram_link_code.py` — `GenerateTelegramLinkCode`: `execute(user_id: UUID) -> str`, returns a signed, time-limited token (via a new `infrastructure/telegram_link.py` helper — see 4.3) containing `user_id`. Does not build the full deep-link URL (that's a presentation-layer concern, mirroring how other use cases don't know about HTTP-level concepts).
- [x] 4.3 `infrastructure/telegram_link.py` — `generate_link_token(user_id: UUID) -> str` and `verify_link_token(token: str) -> UUID`. **Revised after live testing**: the originally-planned `itsdangerous.URLSafeTimedSerializer` approach produced ~102-character tokens, exceeding Telegram's 64-character `start` deep-link parameter limit — links silently failed to carry the payload. Replaced with a compact hand-rolled encoding: base64url(UUID bytes[16] + timestamp bytes[4] + truncated HMAC-SHA256[12]), padding stripped (~43 chars). `verify_link_token` raises `ValueError` on malformed/tampered/expired tokens, using `hmac.compare_digest` for the signature check. See design.md decision 4 for the full story.
- [x] 4.4 `application/event_handlers/notification_dispatch_handler.py` — `NotificationDispatchHandler` with a `handle(self, event: VehicleLocationUpdated) -> None` method whose body is a no-op (mirror `SerTicketTriggerHandler`'s exact docstring/style — no user preference reads, no `SendNotification` calls)
- [x] 4.5 `application/use_cases/list_notification_channels.py` — `ListNotificationChannels`: `execute(user_id: UUID) -> list[str]`, thin delegation returning just the channel names from `config_repo.find_all_by_user_id(user_id)`
- [x] 4.6 `application/use_cases/remove_notification_channel.py` — `RemoveNotificationChannel`: `execute(user_id: UUID, channel: str) -> None`, delegates directly to `config_repo.delete(user_id, channel)` — no provider-side revocation step (see design.md decision 8)

## 5. Presentation layer — schemas and router

- [x] 5.1 Add response schemas to `presentation/api/schemas.py`: `TelegramLinkCodeResponse` (`deep_link: str`), `NotificationChannelsResponse` (`channels: list[str]`)
- [x] 5.2 `presentation/api/routers/notifications.py` — new router:
  - `POST /notifications/telegram/link-code`, `Depends(get_current_user)`: calls `GenerateTelegramLinkCode.execute(current_user.id)`, builds `f"https://t.me/{get_telegram_bot_username()}?start={token}"`, returns `TelegramLinkCodeResponse`
  - `POST /notifications/telegram/webhook` (no auth dependency — public, validated by header instead): reads `X-Telegram-Bot-Api-Secret-Token` header, compares against `get_telegram_webhook_secret()`, returns `401` (or `403`) immediately if it doesn't match. Parses the Telegram update payload for a message matching `/start <token>`; on a valid, unexpired token (via `verify_link_token`, catching `ValueError` for invalid/expired), extracts `user_id`, stores the message's `chat.id` via `UserNotificationChannelConfigRepository.save(user_id, "telegram", NotificationRecipient(data={"chat_id": ...}))`, then sends a confirmation message via `TelegramNotificationChannel.send` (or `SendNotification`, whichever is cleaner — decide during implementation) directly to that chat.
  - `GET /notifications/channels`, `Depends(get_current_user)`: calls `ListNotificationChannels.execute(current_user.id)`, returns `NotificationChannelsResponse(channels=...)`
  - `DELETE /notifications/channels/{channel}`, `Depends(get_current_user)`: calls `RemoveNotificationChannel.execute(current_user.id, channel)`, returns `204 No Content`
- [x] 5.3 Register `notifications_router` in `app.py`

## 6. Wiring — app.py

- [x] 6.1 In `app.py`: construct `TelegramNotificationChannel`, build the `channels: dict[str, NotificationChannelPort]` mapping (`{"telegram": ...}`), construct `PostgresUserNotificationChannelConfigRepository`, `SendNotification`, `GenerateTelegramLinkCode`, `ListNotificationChannels`, `RemoveNotificationChannel`; store on `app.state`
- [x] 6.2 In `app.py`: construct `NotificationDispatchHandler`, subscribe it to `VehicleLocationUpdated` on the existing `InMemoryEventPublisher` instance, alongside the existing `SerTicketTriggerHandler` subscription

## 7. Backend tests

- [x] 7.1 `tests/infrastructure/test_telegram_notification_channel.py` — unit tests for `send()` using `httpx.MockTransport` (mirror `test_elparking_provider.py`'s style): successful send calls the right URL/payload; non-2xx/connection-error responses raise `NotificationChannelApiError`
- [x] 7.2 `tests/infrastructure/test_telegram_link.py` — `generate_link_token`/`verify_link_token` round-trip; expired token raises `ValueError`; tampered token raises `ValueError`; a token generated with a different salt (e.g. the OAuth state serializer) is rejected by `verify_link_token`
- [x] 7.3 `tests/infrastructure/test_user_notification_channel_config_repo_integration.py` — save/find round-trip; `find` returns `None` when absent; `find_all_by_user_id` reflects stored rows and returns `[]` for a user with none; confirm the stored `config` column is plain JSON, not encrypted (read it back directly and assert it's human-readable); `delete` removes an existing row and is idempotent when none exists
- [x] 7.4 `tests/application/use_cases/test_send_notification.py` — sends to a configured channel (fake `NotificationChannelPort`), returns `True`; no configured channels returns `False` without raising
- [x] 7.5 `tests/application/use_cases/test_generate_telegram_link_code.py` — returns a token that `verify_link_token` can decode back to the same `user_id`
- [x] 7.6 `tests/application/event_handlers/test_notification_dispatch_handler.py` — handler can be invoked with a `VehicleLocationUpdated` event and produces no observable side effects (minimal test, mirror `test_ser_ticket_trigger_handler.py`'s documented-minimalism style)
- [x] 7.7 `tests/presentation/test_notifications_router.py` — `POST /link-code`: authenticated success returns a deep link containing a token, 401 for anonymous. `POST /webhook`: missing/incorrect secret header rejected without any linking occurring; valid `/start <token>` with correct header stores the recipient and triggers a confirmation send (fake `SendNotification`/`TelegramNotificationChannel`); expired/tampered token rejected without storing anything. `GET /channels`: returns the right list (and empty list) for authenticated users, 401 for anonymous. `DELETE /channels/{channel}`: returns 204, 401 for anonymous without contacting anything.
- [x] 7.8 `tests/application/use_cases/test_list_notification_channels.py` — returns whatever the repo reports
- [x] 7.9 `tests/application/use_cases/test_remove_notification_channel.py` — deletes an existing config; removing an already-absent channel completes without raising

## 8. Verification

- [x] 8.1 Run backend test suite and linters (ruff, mypy)
- [x] 8.2 Document `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_BOT_USERNAME` in `.env.example`
- [ ] 8.3 Manually verify against a real Telegram bot: create a bot via @BotFather, set the webhook (`setWebhook` with the secret token), call `POST /notifications/telegram/link-code`, open the returned deep link in Telegram, confirm the `/start` message results in a stored `chat_id` and a "✅ Linked!" confirmation message actually arriving — this is the live proof that `send()` works end-to-end, not just against a mock
