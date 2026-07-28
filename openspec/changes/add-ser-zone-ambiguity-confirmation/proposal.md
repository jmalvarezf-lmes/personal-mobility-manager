## Why

`find_containing()` compensates for GPS error by treating a location within a configurable tolerance (default 50cm) of a zone's boundary as "inside" that zone (`add-ser-zone-containment-tolerance`), but it stops at the first matching zone in iteration order. When a vehicle's GPS fix lands within tolerance of two different zones at once — e.g. two adjacent zones of different colours sharing a frontier — the system silently picks one and, for owners with `auto_create_ticket` enabled, creates a real, paid SER ticket for a zone it never actually confirmed. This was explicitly flagged as out of scope in `add-ser-zone-containment-tolerance`'s proposal. This change closes that gap for the auto-creation path: when more than one zone plausibly matches, the system asks the vehicle owner to confirm which one via Telegram instead of guessing.

## What Changes

- `SerZoneRepository`/`FindContainingSerZone` gain a way to return **every** zone that matches a location within the containment tolerance, not just the first — needed to detect ambiguity at all.
- In the `auto_create_ticket` flow only: after `DetermineSerTicketRequirement` confirms a ticket is needed for the primary (first-matching) zone, if more than one zone matched, ticket creation pauses. A new `PendingZoneConfirmation` record is persisted (vehicle, primary + alternate zone candidates, creation timestamp) instead of creating the ticket immediately.
- `TelegramNotificationChannel` gains the ability to send a message with an inline keyboard (one button per candidate zone, plus a Cancel button).
- The existing `POST /notifications/telegram/webhook` endpoint gains handling for incoming `callback_query` updates (in addition to its current `message` handling for account linking), resolving a tapped button back to its `PendingZoneConfirmation` and either creating the ticket for the chosen zone or cancelling.
- **BREAKING**: `SerTicketProviderPort.create_ticket` and `CreateSerTicket.execute` gain a way to force ticket creation against an explicit zone, bypassing that call's own internal zone re-resolution — required so a confirmed zone choice is actually honored rather than re-derived from location and potentially landing on a different zone again.
- A new `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` env var (default `10`) bounds how long a `PendingZoneConfirmation` stays open. A new scheduled sweep job (same `BackgroundScheduler` "interval" pattern as `SessionCleanupScheduler`) expires stale ones on a short interval.
- Tapping Cancel, or letting a confirmation time out, both result in: no ticket created, and one notification to the owner explaining why (reason: `cancelled` or `timed_out`) — mirrors the existing `possibly_created` boolean pattern used by the ticket-creation-failed notification, rather than two separate templates.
- A `VehicleLocationUpdated` event for a vehicle with an already-pending confirmation supersedes it: the old pending confirmation is silently cancelled (no "cancelled" notification for this case) and a fresh one is created for the vehicle's current candidates. The superseded Telegram button, if tapped later, must be recognized as stale and rejected via `answerCallbackQuery` rather than acted on.
- Out of scope: the manual (non-auto-create) `ser_zone_ticket_required` notification and `POST /parking/ser-tickets` flow are unaffected — a user creating a ticket manually already sees the app and picks for themselves.

## Capabilities

### New Capabilities
- `ser-zone-ambiguity-confirmation`: detecting multiple candidate SER zones for one location, persisting a pending confirmation, sending/receiving the Telegram confirm-or-cancel interaction, resolving it into ticket creation or cancellation, and expiring unanswered confirmations on a timeout.

### Modified Capabilities
- `ser-zone-query`: `SerZoneRepository`/`FindContainingSerZone` gain the ability to return all tolerance-matching zone candidates for a location, not only the first match.
- `ser-ticket-auto-creation`: `SerTicketCreationTriggerHandler` no longer creates a ticket immediately when the matched zone is ambiguous — it defers to the new confirmation flow instead.
- `ser-ticket-provider`: `SerTicketProviderPort.create_ticket` and `CreateSerTicket.execute` gain an explicit-zone override that bypasses internal zone re-resolution.
- `notification-channel`: `TelegramNotificationChannel` gains inline-keyboard message sending, and the Telegram webhook gains `callback_query` handling alongside its existing `message` handling.

## Impact

- **Code**: `domain/ports/ser_zone_repository.py`, `application/use_cases/find_containing_ser_zone.py`, `infrastructure/repositories/postgres/ser_zone_repo.py` (candidate-listing); a new `PendingZoneConfirmation` domain entity + port + Postgres repository + Alembic migration; `application/event_handlers/ser_ticket_creation_trigger_handler.py` (ambiguity branch); `application/event_handlers/ser_ticket_notification_trigger_handler.py` or a new handler (confirmation/timeout notifications); `infrastructure/notification_channels/telegram/channel.py` (inline keyboard); `presentation/api/routers/notifications.py` (`callback_query` handling); `application/use_cases/create_ser_ticket.py`, `domain/ports/ser_ticket_provider.py`, `infrastructure/ser_ticket_providers/elparking/provider.py` (explicit-zone override); `infrastructure/scheduler.py` (new expiry sweep job); `config.py` (new env var); `presentation/api/app.py` (wiring).
- **Behavior**: Only affects vehicles whose owner has `auto_create_ticket` enabled. Introduces a real time window (up to the configured timeout) during which a vehicle in an ambiguous zone is not yet ticketed while waiting for the owner's Telegram reply.
- **Config surface**: one new environment variable, `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES`, default `10`.
- **Breaking change**: `SerTicketProviderPort.create_ticket`'s signature changes to accept an optional explicit zone; any future provider implementation must support it.
