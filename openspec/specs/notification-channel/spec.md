### Requirement: NotificationRecipient and NotificationMessage value objects
The system SHALL define `NotificationRecipient` (wrapping `data: dict[str, Any]`, channel-defined contents) and `NotificationMessage` (`text: str`) as frozen domain value objects.

#### Scenario: Value objects are immutable
- **WHEN** a `NotificationRecipient` or `NotificationMessage` is constructed
- **THEN** it is a frozen dataclass (or equivalent) holding exactly the values it was given

---

### Requirement: NotificationChannelPort defines a channel-agnostic send method
The system SHALL define `NotificationChannelPort` with an abstract `send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None` method. The port SHALL NOT define any account-linking or connection-establishment method — those are channel-specific concerns, not part of this shared interface.

#### Scenario: Port is implementation-agnostic
- **WHEN** a concrete class implements `NotificationChannelPort`
- **THEN** it may define any internal structure for the `data` inside `NotificationRecipient` it expects, without changing the port's method signature

---

### Requirement: user_notification_channel_configs table persists per-user channel configuration
The system SHALL create a `user_notification_channel_configs` table with columns: `user_id UUID NOT NULL REFERENCES users(id)`, `channel TEXT NOT NULL`, `config TEXT NOT NULL` (JSON-serialized, stored in cleartext — not encrypted, since channel identifiers like a Telegram `chat_id` are not credentials), `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`, with a composite primary key on `(user_id, channel)`.

#### Scenario: Table schema
- **WHEN** the migration is applied
- **THEN** the `user_notification_channel_configs` table exists with all four columns and a composite primary key on `(user_id, channel)`

---

### Requirement: UserNotificationChannelConfigRepository stores, retrieves, and deletes channel configuration
The system SHALL define a `UserNotificationChannelConfigRepository` port with:
- `save(user_id: UUID, channel: str, recipient: NotificationRecipient) -> None` — JSON-serializes `recipient.data` (no encryption) and upserts the row for `(user_id, channel)`
- `find(user_id: UUID, channel: str) -> NotificationRecipient | None` — returns the deserialized recipient, or `None` if none exists
- `find_all_by_user_id(user_id: UUID) -> list[tuple[str, NotificationRecipient]]` — returns all configured channels and their recipients for a user
- `delete(user_id: UUID, channel: str) -> None` — removes the stored config for `(user_id, channel)`, if present. SHALL NOT raise if no such row exists (idempotent).

#### Scenario: Save then find round-trips the recipient
- **WHEN** `save` is called with a `NotificationRecipient` for a `(user_id, channel)` pair, followed by `find` for the same pair
- **THEN** `find` returns a `NotificationRecipient` whose `data` equals what was saved

#### Scenario: find returns None when no config exists
- **WHEN** `find` is called for a `(user_id, channel)` pair with no stored row
- **THEN** it returns `None` without raising

#### Scenario: find_all_by_user_id reflects all of a user's configured channels
- **WHEN** a user has a stored config for `"telegram"` and no other channel
- **THEN** `find_all_by_user_id` returns exactly one entry, for `"telegram"`

#### Scenario: Delete removes an existing config
- **WHEN** `delete` is called for a `(user_id, channel)` pair with a stored config
- **THEN** a subsequent `find` for the same pair returns `None`

#### Scenario: Delete is idempotent
- **WHEN** `delete` is called for a `(user_id, channel)` pair with no stored config
- **THEN** it completes without raising

---

### Requirement: TelegramNotificationChannel implements send via the Telegram Bot API
The system SHALL provide `TelegramNotificationChannel`, implementing `NotificationChannelPort.send`, which calls Telegram's `sendMessage` Bot API endpoint using the `chat_id` from `recipient.data` and the text from `message.text`.

#### Scenario: Successful send calls the Telegram API
- **WHEN** `send` is called with a recipient containing a valid `chat_id`
- **THEN** a request is made to Telegram's `sendMessage` endpoint with that `chat_id` and the message text

#### Scenario: Send failure does not raise an unhandled exception type
- **WHEN** the Telegram API is unreachable or returns an error response
- **THEN** the failure is raised as a clearly identifiable exception, not a raw, unwrapped HTTP client exception

---

### Requirement: Telegram account linking uses a signed, time-limited deep-link token
The system SHALL expose `POST /notifications/telegram/link-code`, requiring an authenticated session, which generates a signed, time-limited token (containing the current user's id) and returns a Telegram deep link (`https://t.me/<bot_username>?start=<token>`). The token's encoding SHALL be distinct from the session JWT and the OAuth CSRF state token, so a token generated for one purpose cannot be verified as another. The token SHALL be at most 64 characters, since this is the maximum length Telegram accepts for the `start` deep-link parameter — a longer token silently fails to be delivered to the bot at all.

#### Scenario: Authenticated user receives a deep link
- **WHEN** an authenticated user calls `POST /notifications/telegram/link-code`
- **THEN** the response contains a Telegram deep link with a signed token identifying that user
- **THEN** the token portion of that deep link is at most 64 characters long

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `POST /notifications/telegram/link-code`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Telegram webhook validates authenticity and completes linking
The system SHALL expose `POST /notifications/telegram/webhook`, which SHALL reject any request whose `X-Telegram-Bot-Api-Secret-Token` header does not match the configured webhook secret. For a valid request containing a `/start <token>` message, it SHALL verify and decode the token (rejecting expired or tampered tokens), extract the user id, and store the message's `chat.id` as that user's Telegram `NotificationRecipient`. On successful linking, it SHALL send a confirmation message to the linked chat via `NotificationChannelPort.send`.

#### Scenario: Valid linking request stores the chat_id and confirms
- **WHEN** the webhook receives a request with the correct secret header and a valid, unexpired `/start <token>` message
- **THEN** the sender's `chat_id` is stored as the token's user's Telegram recipient
- **THEN** a confirmation message is sent to that chat

#### Scenario: Requests without the correct secret header are rejected
- **WHEN** the webhook receives a request with a missing or incorrect `X-Telegram-Bot-Api-Secret-Token` header
- **THEN** the request is rejected and no linking occurs

#### Scenario: Expired or tampered tokens are rejected
- **WHEN** the webhook receives a `/start <token>` message where the token has expired or fails signature verification
- **THEN** no linking occurs and no chat_id is stored

---

### Requirement: SendNotification sends to all of a user's configured channels
The system SHALL define `SendNotification` with `execute(user_id: UUID, text: str) -> bool`, which sends `text` to every channel configured for `user_id` (via `UserNotificationChannelConfigRepository.find_all_by_user_id`), returning `True` if at least one send succeeded and `False` if the user has no configured channels. No channel-preference logic is applied — all configured channels receive the message.

#### Scenario: Message sent to a user's configured channel
- **WHEN** `execute` is called for a user with a configured Telegram channel
- **THEN** `TelegramNotificationChannel.send` is called with that user's stored recipient and the given text
- **THEN** `execute` returns `True`

#### Scenario: No configured channels returns False without error
- **WHEN** `execute` is called for a user with no configured notification channels
- **THEN** it returns `False` without raising

---

### Requirement: ListNotificationChannels reports a user's configured channels
The system SHALL define `ListNotificationChannels` with `execute(user_id: UUID) -> list[str]`, returning the channel names for which `user_id` has a stored configuration.

#### Scenario: Reports currently configured channels
- **WHEN** `execute` is called for a user with a configured Telegram channel
- **THEN** it returns `["telegram"]`

#### Scenario: Reports an empty list for a user with no configured channels
- **WHEN** `execute` is called for a user with no configured channels
- **THEN** it returns `[]`

---

### Requirement: RemoveNotificationChannel deletes a user's channel configuration
The system SHALL define `RemoveNotificationChannel` with `execute(user_id: UUID, channel: str) -> None`, deleting the stored configuration for `(user_id, channel)` via `UserNotificationChannelConfigRepository.delete`. Unlike SER provider disconnection, no server-side revocation is attempted — there is no equivalent operation for a channel like Telegram, where the bot has no API to invalidate a chat_id.

#### Scenario: Removing a configured channel deletes it
- **WHEN** `execute` is called for a `(user_id, channel)` pair with a stored configuration
- **THEN** the configuration is deleted
- **THEN** a subsequent `ListNotificationChannels.execute` for that user no longer includes that channel

#### Scenario: Removing an already-absent channel is a no-op success
- **WHEN** `execute` is called for a `(user_id, channel)` pair with no stored configuration
- **THEN** it completes without raising

---

### Requirement: Authenticated user can list their configured notification channels
The system SHALL expose `GET /notifications/channels`, requiring an authenticated session, returning `{"channels": [<channel names>]}` for the current user.

#### Scenario: Returns configured channels
- **WHEN** an authenticated user with a configured Telegram channel calls `GET /notifications/channels`
- **THEN** the response is `200 OK` with `{"channels": ["telegram"]}`

#### Scenario: Returns an empty list when nothing is configured
- **WHEN** an authenticated user with no configured channels calls `GET /notifications/channels`
- **THEN** the response is `200 OK` with `{"channels": []}`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `GET /notifications/channels`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can delete a configured notification channel
The system SHALL expose `DELETE /notifications/channels/{channel}`, requiring an authenticated session, calling `RemoveNotificationChannel.execute` for the current user and the path's `channel`. It SHALL respond `204 No Content` on success — no server-side revocation step exists to report on, unlike the SER provider disconnect endpoint.

#### Scenario: Successful deletion
- **WHEN** an authenticated user deletes a configured channel
- **THEN** the response is `204 No Content`
- **THEN** a subsequent `GET /notifications/channels` no longer lists that channel

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `DELETE /notifications/channels/{channel}`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: A no-op handler is subscribed to VehicleLocationUpdated as notification-wiring scaffolding
The system SHALL register a notification-dispatch event handler as a subscriber to `VehicleLocationUpdated` at application startup. Its handling logic SHALL be a no-op in this change — it SHALL NOT read user preferences, SHALL NOT decide when to notify, and SHALL NOT call `SendNotification`.

#### Scenario: Handler is invoked but performs no action
- **WHEN** a `VehicleLocationUpdated` event is published
- **THEN** the notification-dispatch handler is invoked
- **THEN** no notification is sent and no other observable state changes as a result
