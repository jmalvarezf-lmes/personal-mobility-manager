## ADDED Requirements

### Requirement: Authenticated user can list the system's available notification channels
The system SHALL expose `GET /notifications/available-channels`, requiring an authenticated session, returning `{"channels": [<channel names>]}` — the ids of every channel registered in the running system (independent of what any particular user has configured).

#### Scenario: Returns the registered channels
- **WHEN** an authenticated user calls `GET /notifications/available-channels`
- **THEN** the response is `200 OK` with `{"channels": ["telegram"]}`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie is sent to `GET /notifications/available-channels`
- **THEN** the response is `401 Unauthorized`

### Requirement: Connecting a channel auto-selects it as preferred when none is set
The system SHALL, immediately after successfully storing a user's configuration for a channel (e.g. on successful Telegram linking), set that user's `preferred_notification_channel` (in `user_preferences`) to the newly connected channel if and only if no preferred channel is currently set for that user.

#### Scenario: First channel connected becomes preferred
- **WHEN** a user with no `preferred_notification_channel` set successfully connects the Telegram channel
- **THEN** the user's `preferred_notification_channel` becomes `"telegram"`

#### Scenario: Connecting an additional channel does not override an existing preference
- **WHEN** a user with `preferred_notification_channel` already set to some channel successfully connects a different channel
- **THEN** the user's `preferred_notification_channel` remains unchanged

## MODIFIED Requirements

### Requirement: SendNotification sends to a user's preferred channel only
The system SHALL define `SendNotification` with `execute(user_id: UUID, text: str) -> bool`, which sends `text` via the single channel identified by that user's `preferred_notification_channel` preference, if it is set and a configuration exists for that `(user_id, channel)` pair (via `UserNotificationChannelConfigRepository.find`). It returns `True` if the send succeeded. It SHALL NOT fall back to any other configured channel and SHALL NOT send to more than one channel. It returns `False` without raising if `preferred_notification_channel` is unset, or if it is set but no configuration exists for that channel (a stale preference).

#### Scenario: Message sent to the user's preferred, connected channel
- **WHEN** `execute` is called for a user whose `preferred_notification_channel` is `"telegram"` and who has a stored Telegram configuration
- **THEN** `TelegramNotificationChannel.send` is called with that user's stored recipient and the given text
- **THEN** `execute` returns `True`

#### Scenario: No preferred channel set returns False without error
- **WHEN** `execute` is called for a user with no `preferred_notification_channel` set
- **THEN** it returns `False` without raising and without sending anything

#### Scenario: Stale preferred channel (no longer connected) returns False without error
- **WHEN** `execute` is called for a user whose `preferred_notification_channel` is set to a channel for which no configuration exists (e.g. it was disconnected)
- **THEN** it returns `False` without raising and without sending anything
- **THEN** no other configured channel the user might have is used as a fallback

### Requirement: RemoveNotificationChannel deletes a user's channel configuration
The system SHALL define `RemoveNotificationChannel` with `execute(user_id: UUID, channel: str) -> None`, deleting the stored configuration for `(user_id, channel)` via `UserNotificationChannelConfigRepository.delete`. Unlike SER provider disconnection, no server-side revocation is attempted — there is no equivalent operation for a channel like Telegram, where the bot has no API to invalidate a chat_id. If the removed channel equals the user's current `preferred_notification_channel`, the preference SHALL also be cleared to `None` in the same operation.

#### Scenario: Removing a configured channel deletes it
- **WHEN** `execute` is called for a `(user_id, channel)` pair with a stored configuration
- **THEN** the configuration is deleted
- **THEN** a subsequent `ListNotificationChannels.execute` for that user no longer includes that channel

#### Scenario: Removing an already-absent channel is a no-op success
- **WHEN** `execute` is called for a `(user_id, channel)` pair with no stored configuration
- **THEN** it completes without raising

#### Scenario: Removing the user's preferred channel clears the preference
- **WHEN** `execute` is called for a `(user_id, channel)` pair where `channel` equals that user's current `preferred_notification_channel`
- **THEN** the configuration is deleted
- **THEN** the user's `preferred_notification_channel` becomes `None`

#### Scenario: Removing a non-preferred channel leaves the preference untouched
- **WHEN** `execute` is called for a `(user_id, channel)` pair where `channel` does not equal that user's current `preferred_notification_channel`
- **THEN** the configuration is deleted
- **THEN** the user's `preferred_notification_channel` remains unchanged
