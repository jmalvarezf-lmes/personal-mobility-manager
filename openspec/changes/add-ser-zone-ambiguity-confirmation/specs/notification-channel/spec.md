## MODIFIED Requirements

### Requirement: NotificationRecipient and NotificationMessage value objects
The system SHALL define `NotificationRecipient` (wrapping `data: dict[str, Any]`, channel-defined contents) and `NotificationMessage` (`text: str`, `location: GeoLocation | None`, defaulting to `None`, and `actions: list[NotificationAction] | None`, defaulting to `None`) as frozen domain value objects. `NotificationAction` SHALL be a frozen value object with `label: str` and `callback_data: str`. `actions` is an optional, channel-agnostic hint — a channel implementation MAY render it as interactive buttons if it supports replies, and MUST otherwise ignore it (sending only `text`, unaffected) rather than erroring.

#### Scenario: Value objects are immutable
- **WHEN** a `NotificationRecipient`, `NotificationMessage`, or `NotificationAction` is constructed
- **THEN** it is a frozen dataclass (or equivalent) holding exactly the values it was given

#### Scenario: NotificationMessage can carry an optional location
- **WHEN** a `NotificationMessage` is constructed with a `GeoLocation`
- **THEN** its `location` field holds that value
- **WHEN** a `NotificationMessage` is constructed without a `location` argument
- **THEN** its `location` field is `None`

#### Scenario: NotificationMessage can carry optional actions
- **WHEN** a `NotificationMessage` is constructed with a list of `NotificationAction`
- **THEN** its `actions` field holds that list
- **WHEN** a `NotificationMessage` is constructed without an `actions` argument
- **THEN** its `actions` field is `None`

#### Scenario: A channel without reply support ignores actions rather than erroring
- **WHEN** `NotificationChannelPort.send` is called on an implementation that does not support interactive replies, with a message whose `actions` is not `None`
- **THEN** the message's `text` (and `location`, if set) is still sent, and no exception is raised because `actions` was present

---

### Requirement: TelegramNotificationChannel implements send via the Telegram Bot API
The system SHALL provide `TelegramNotificationChannel`, implementing `NotificationChannelPort.send`, which calls Telegram's `sendMessage` Bot API endpoint using the `chat_id` from `recipient.data` and the text from `message.text`. If `message.location` is set, it SHALL additionally call Telegram's `sendLocation` Bot API endpoint with that `chat_id` and the location's latitude/longitude, as a separate API call — Telegram's `sendLocation` endpoint has no caption parameter, so a message with both text and a location results in two Telegram API calls, not one. If `message.actions` is set, the `sendMessage` call SHALL include a `reply_markup` with an `inline_keyboard`: one button per `NotificationAction`, each with that action's `label` as its button text and `callback_data` as its callback payload.

#### Scenario: Successful send calls the Telegram API
- **WHEN** `send` is called with a recipient containing a valid `chat_id` and a message with no `location` and no `actions`
- **THEN** a request is made to Telegram's `sendMessage` endpoint with that `chat_id` and the message text, with no `reply_markup`
- **THEN** no request is made to Telegram's `sendLocation` endpoint

#### Scenario: Send failure does not raise an unhandled exception type
- **WHEN** the Telegram API is unreachable or returns an error response
- **THEN** the failure is raised as a clearly identifiable exception, not a raw, unwrapped HTTP client exception

#### Scenario: Message with a location sends both a text message and a location pin
- **WHEN** `send` is called with a message whose `location` is set
- **THEN** a request is made to Telegram's `sendMessage` endpoint with the message text
- **THEN** a separate request is made to Telegram's `sendLocation` endpoint with that `chat_id` and the location's latitude/longitude

#### Scenario: Message with actions sends an inline keyboard
- **WHEN** `send` is called with a message whose `actions` contains one or more `NotificationAction` entries
- **THEN** the `sendMessage` request includes a `reply_markup` with one inline keyboard button per action, using that action's `label` and `callback_data`

---

### Requirement: Telegram webhook validates authenticity and completes linking
The system SHALL expose `POST /notifications/telegram/webhook`, which SHALL reject any request whose `X-Telegram-Bot-Api-Secret-Token` header does not match the configured webhook secret. For a valid request containing a `/start <token>` message, it SHALL verify and decode the token (rejecting expired or tampered tokens), extract the user id, and store the message's `chat.id` as that user's Telegram `NotificationRecipient`. On successful linking, it SHALL send a confirmation message to the linked chat via `NotificationChannelPort.send`, with text rendered via the notification-template mechanism using that user's `notification_language` preference (falling back to the default language if unset). A valid request containing a `callback_query` (rather than a `message`) SHALL be routed to the zone-confirmation handling described in the `ser-zone-ambiguity-confirmation` capability instead of the linking flow above.

#### Scenario: Valid linking request stores the chat_id and confirms
- **WHEN** the webhook receives a request with the correct secret header and a valid, unexpired `/start <token>` message
- **THEN** the sender's `chat_id` is stored as the token's user's Telegram recipient
- **THEN** a confirmation message is sent to that chat, localized to that user's `notification_language`

#### Scenario: Requests without the correct secret header are rejected
- **WHEN** the webhook receives a request with a missing or incorrect `X-Telegram-Bot-Api-Secret-Token` header
- **THEN** the request is rejected and no linking occurs, and no zone-confirmation handling occurs

#### Scenario: Expired or tampered tokens are rejected
- **WHEN** the webhook receives a `/start <token>` message where the token has expired or fails signature verification
- **THEN** no linking occurs and no chat_id is stored

#### Scenario: Confirmation falls back to the default language when unset
- **WHEN** the linking user has no `notification_language` preference set
- **THEN** the confirmation message is rendered in the default language

#### Scenario: A callback_query update is routed away from the linking flow
- **WHEN** the webhook receives a valid (secret-authenticated) request whose body contains `callback_query` rather than `message`
- **THEN** the `/start <token>` linking logic is not invoked for that request
