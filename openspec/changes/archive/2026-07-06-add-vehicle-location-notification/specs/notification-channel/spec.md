## MODIFIED Requirements

### Requirement: NotificationRecipient and NotificationMessage value objects
The system SHALL define `NotificationRecipient` (wrapping `data: dict[str, Any]`, channel-defined contents) and `NotificationMessage` (`text: str`, `location: GeoLocation | None`, defaulting to `None`) as frozen domain value objects.

#### Scenario: Value objects are immutable
- **WHEN** a `NotificationRecipient` or `NotificationMessage` is constructed
- **THEN** it is a frozen dataclass (or equivalent) holding exactly the values it was given

#### Scenario: NotificationMessage can carry an optional location
- **WHEN** a `NotificationMessage` is constructed with a `GeoLocation`
- **THEN** its `location` field holds that value
- **WHEN** a `NotificationMessage` is constructed without a `location` argument
- **THEN** its `location` field is `None`

### Requirement: TelegramNotificationChannel implements send via the Telegram Bot API
The system SHALL provide `TelegramNotificationChannel`, implementing `NotificationChannelPort.send`, which calls Telegram's `sendMessage` Bot API endpoint using the `chat_id` from `recipient.data` and the text from `message.text`. If `message.location` is set, it SHALL additionally call Telegram's `sendLocation` Bot API endpoint with that `chat_id` and the location's latitude/longitude, as a separate API call — Telegram's `sendLocation` endpoint has no caption parameter, so a message with both text and a location results in two Telegram API calls, not one.

#### Scenario: Successful send calls the Telegram API
- **WHEN** `send` is called with a recipient containing a valid `chat_id` and a message with no `location`
- **THEN** a request is made to Telegram's `sendMessage` endpoint with that `chat_id` and the message text
- **THEN** no request is made to Telegram's `sendLocation` endpoint

#### Scenario: Send failure does not raise an unhandled exception type
- **WHEN** the Telegram API is unreachable or returns an error response
- **THEN** the failure is raised as a clearly identifiable exception, not a raw, unwrapped HTTP client exception

#### Scenario: Message with a location sends both a text message and a location pin
- **WHEN** `send` is called with a message whose `location` is set
- **THEN** a request is made to Telegram's `sendMessage` endpoint with the message text
- **THEN** a separate request is made to Telegram's `sendLocation` endpoint with that `chat_id` and the location's latitude/longitude

### Requirement: Telegram webhook validates authenticity and completes linking
The system SHALL expose `POST /notifications/telegram/webhook`, which SHALL reject any request whose `X-Telegram-Bot-Api-Secret-Token` header does not match the configured webhook secret. For a valid request containing a `/start <token>` message, it SHALL verify and decode the token (rejecting expired or tampered tokens), extract the user id, and store the message's `chat.id` as that user's Telegram `NotificationRecipient`. On successful linking, it SHALL send a confirmation message to the linked chat via `NotificationChannelPort.send`, with text rendered via the notification-template mechanism using that user's `notification_language` preference (falling back to the default language if unset).

#### Scenario: Valid linking request stores the chat_id and confirms
- **WHEN** the webhook receives a request with the correct secret header and a valid, unexpired `/start <token>` message
- **THEN** the sender's `chat_id` is stored as the token's user's Telegram recipient
- **THEN** a confirmation message is sent to that chat, localized to that user's `notification_language`

#### Scenario: Requests without the correct secret header are rejected
- **WHEN** the webhook receives a request with a missing or incorrect `X-Telegram-Bot-Api-Secret-Token` header
- **THEN** the request is rejected and no linking occurs

#### Scenario: Expired or tampered tokens are rejected
- **WHEN** the webhook receives a `/start <token>` message where the token has expired or fails signature verification
- **THEN** no linking occurs and no chat_id is stored

#### Scenario: Confirmation falls back to the default language when unset
- **WHEN** the linking user has no `notification_language` preference set
- **THEN** the confirmation message is rendered in the default language

### Requirement: SendNotification delivers a pre-built message to a user's preferred channel only
The system SHALL define `SendNotification` with `execute(user_id: UUID, message: NotificationMessage) -> bool`, which delivers the given `message` via the single channel identified by that user's `preferred_notification_channel` preference, if it is set and a configuration exists for that `(user_id, channel)` pair (via `UserNotificationChannelConfigRepository.find`). It returns `True` if the send succeeded. It SHALL NOT fall back to any other configured channel and SHALL NOT send to more than one channel. It returns `False` without raising if `preferred_notification_channel` is unset, or if it is set but no configuration exists for that channel (a stale preference). `SendNotification` SHALL NOT build message text itself, look up templates, or resolve language preferences — callers pass a fully-formed `NotificationMessage`.

#### Scenario: Message sent to the user's preferred, connected channel
- **WHEN** `execute` is called for a user whose `preferred_notification_channel` is `"telegram"` and who has a stored Telegram configuration, with a pre-built `NotificationMessage`
- **THEN** `TelegramNotificationChannel.send` is called with that user's stored recipient and the given message
- **THEN** `execute` returns `True`

#### Scenario: No preferred channel set returns False without error
- **WHEN** `execute` is called for a user with no `preferred_notification_channel` set
- **THEN** it returns `False` without raising and without sending anything

#### Scenario: Stale preferred channel (no longer connected) returns False without error
- **WHEN** `execute` is called for a user whose `preferred_notification_channel` is set to a channel for which no configuration exists (e.g. it was disconnected)
- **THEN** it returns `False` without raising and without sending anything
- **THEN** no other configured channel the user might have is used as a fallback

## ADDED Requirements

### Requirement: Notification templates render localized text for a small, closed set of message kinds
The system SHALL provide a notification-template rendering function accepting a message kind, a language code (or `None`), and keyword substitution values, returning the rendered text for that kind in the given language. If the language is `None` or not among the supported languages, the function SHALL render using a default language rather than raising. This mechanism SHALL NOT be a general-purpose i18n framework (no `.po`/`.mo` compilation, no `gettext` dependency) — it covers exactly the message kinds this system defines.

#### Scenario: Renders a known kind in a supported language
- **WHEN** the template function is called with a message kind and a supported language code, plus any required substitution values
- **THEN** it returns that kind's text rendered in that language with the values substituted

#### Scenario: Unset or unsupported language falls back to the default
- **WHEN** the template function is called with `language=None` or a language code not among the supported set
- **THEN** it returns that kind's text rendered in the default language, without raising

## REMOVED Requirements

### Requirement: A no-op handler is subscribed to VehicleLocationUpdated as notification-wiring scaffolding
**Reason**: Superseded by the `vehicle-location-notification` capability, which defines the notification-dispatch handler's real behavior (movement-threshold detection, message construction, and dispatch via `SendNotification`).
**Migration**: See `vehicle-location-notification`'s spec for the handler's actual behavior. No data migration needed — this was scaffolding with no persisted state of its own.
