## Context

`SerZoneRepository.find_containing()` applies a configurable containment tolerance (default 50cm, `add-ser-zone-containment-tolerance`) and returns the **first** zone in iteration order whose polygon covers the location or is within tolerance of it. Two callers depend on this: `FindContainingSerZone` (notification path) and `ElParkingSerTicketProvider.create_ticket()` (re-resolves the zone again, internally, from the location it's given). When two zones both satisfy the tolerance check at once — adjacent zones sharing a frontier, possibly different colours/prices — `find_containing()` never surfaces the second one. For owners with `UserPreferences.auto_create_ticket = true`, `SerTicketCreationTriggerHandler` acts on that single answer unattended and creates a real, paid ticket with no human in the loop at all.

This design only touches the auto-create path. The manual path (`ser_zone_ticket_required` notification, `POST /parking/ser-tickets`) already puts a human — looking at the app — in the loop, so it's left untouched.

Existing building blocks this reuses rather than reinvents:
- `POST /notifications/telegram/webhook` already receives Telegram updates (secret-token authenticated) and already has `app.state` access to channels, config repos, and preferences — currently it only branches on `update["message"]` for the `/start <token>` linking flow.
- `SessionCleanupScheduler` already establishes the "APScheduler `BackgroundScheduler`, one `add_job("interval", ...)`, calls a use case, never raises" pattern for a periodic sweep of expired rows.
- `on_ticket_creation_failed`'s `possibly_created: bool` already establishes the "one template, a reason flag branches the wording" pattern instead of one template per outcome.

## Goals / Non-Goals

**Goals:**
- Detect, at the moment a ticket would be auto-created, whether more than one SER zone plausibly matches the vehicle's location.
- When ambiguous, ask the owner via Telegram which zone is correct (or to cancel) before any ticket is created.
- Guarantee "no answer, no ticket" — an unanswered or explicitly cancelled confirmation never results in a paid ticket.
- Keep the manual ticket-creation flow (`POST /parking/ser-tickets`, the `ser_zone_ticket_required` notification) completely unchanged.

**Non-Goals:**
- Disambiguating for owners without `auto_create_ticket` enabled.
- Supporting confirmation over any channel other than Telegram — other channels degrade to a plain notice with no way to reply (see Risks).
- Changing enforcement-schedule, exemption, or active-ticket short-circuit logic in `DetermineSerTicketRequirement` — it still runs once, against the primary zone only.
- General-purpose "interactive notification" infrastructure beyond what this one flow needs.

## Decisions

### D1: `find_containing()` gains a sibling that returns *all* candidates, not a changed return type
Add `SerZoneRepository.find_all_containing(location) -> list[SerZone]` (ordered the same way `find_containing()` iterates today, so `candidates[0]` is exactly what `find_containing()` already returns). `find_containing()` itself is reimplemented as `find_all_containing(location)[0] if candidates else None` so its existing callers and tests are untouched. `ElParkingSerTicketProvider.create_ticket()` keeps calling `find_containing()` — it never needs the candidate list, only the (possibly overridden) single zone.
- Alternative rejected: changing `find_containing()`'s return type to `list[SerZone]` — would ripple into every existing caller and test for a capability only one new caller needs.

### D2: Ambiguity is checked only after `DetermineSerTicketRequirement` says yes, and only against the primary zone
`SerTicketCreationTriggerHandler` calls `find_all_containing()`, runs `DetermineSerTicketRequirement.execute(candidates[0], ...)` exactly as today, and only branches into the confirmation flow if that returns `True` *and* `len(candidates) > 1`. If the primary zone doesn't need a ticket, the handler returns exactly as today — the alternates are never considered, even if one of them would need a ticket.
- Alternative rejected: running `DetermineSerTicketRequirement` against every candidate — turns a rare edge case into an expensive per-event fan-out (enforcement schedule + exemption + ambient-label lookups × N candidates) for a scenario (a required ticket in zone A but not zone B, both within the same few dozen centimetres) that the tolerance value's own rationale (GPS error) makes implausible in practice; can be revisited if it ever occurs.

### D3: A new `pending_zone_confirmations` table, not an in-memory or Redis-backed structure
The gap between "message sent" and "button tapped" is unbounded up to the timeout (10 minutes default) and must survive process restarts/multiple app workers. A row per pending confirmation: `id (uuid pk)`, `vehicle_id`, `user_id`, `city_code`, candidate list as JSONB (`[{zone_number, zone_type, district}, ...]`, index 0 is primary), `latitude`/`longitude` (the location `CreateSerTicket` needs), `status` (`pending` / `confirmed` / `cancelled` / `timed_out` / `superseded`), `created_at`, `expires_at`, `resolved_at`. Indexed on `(vehicle_id) WHERE status = 'pending'` (supersession lookup) and `(status, expires_at)` (sweep query).
- Telegram `chat_id` is deliberately **not** stored on the row — the callback that answers a button arrives on the same webhook with its own `chat_id` in the payload; the row only needs to be looked up by the id encoded in `callback_data`.

### D4: `callback_data` encodes `(confirmation_id, candidate_index | "x")`, nothing else
Format: `zc:<uuid.hex>:<index>` or `zc:<uuid.hex>:x` for Cancel. `uuid.hex` (32 chars, no dashes) keeps the whole token well under Telegram's 64-byte `callback_data` limit even with headroom for future fields. The webhook looks the row up by id, checks `status == "pending"` and `now < expires_at`, and only then acts — an expired-but-not-yet-swept row is treated as already timed out (rejected via `answerCallbackQuery`'s alert text), so the sweep job's cadence is a housekeeping/notification-latency concern, not a correctness one.

### D5: Explicit-zone override threaded through the provider port, not resolved a second time
`SerTicketProviderPort.create_ticket()` and `CreateSerTicket.execute()` each gain an optional `zone: SerZone | None = None` parameter (default preserves current behavior exactly). `ElParkingSerTicketProvider.create_ticket()` changes its one line — `ser_zone = zone or self._ser_zone_repo.find_containing(location)` — instead of always re-deriving the zone from `location`. This is the only way a confirmed zone choice is guaranteed to be honored: re-running `find_containing(location)` after confirmation would hit the exact same ambiguity and could silently land back on the *other* zone.
- Alternative rejected: encoding the chosen zone into `location` somehow (e.g. nudging the coordinate) — fragile, and misrepresents the vehicle's real GPS position in stored data.

### D6: Ticket-creation-from-confirmation reuses `SerTicketCreationTriggerHandler`'s existing provider-resolution/event-publishing logic via a new application use case, not a copy in the webhook router
Extract the current `_create_ticket` helper's shape (resolve connected provider, resolve `default_ticket_duration_minutes`, call `CreateSerTicket.execute`, publish `SerTicketCreated`/`SerTicketCreationFailed`) into a new `application/use_cases/resolve_pending_zone_confirmation.py` (`ResolvePendingZoneConfirmation`), taking `(confirmation_id, chosen_index | None)`. `chosen_index = None` means Cancel. The webhook router calls this one use case for both outcomes — it does not orchestrate provider lookups or event publishing itself, keeping the "routers call use cases only" rule intact. `SerTicketCreationTriggerHandler._create_ticket` and this use case both end up calling the same small provider/duration-resolution logic; whichever is implemented first factors it out for the other to reuse.
- This also means a ticket created via confirmation publishes the exact same `SerTicketCreated` event as one created directly — `SerTicketNotificationTriggerHandler.on_ticket_created` needs no changes to notify the owner "ticket created" either way.

### D7: Cancel and timeout are one event, one template, a `reason` field — not two
A new `SerZoneConfirmationDismissed` domain event (`vehicle_id`, `user_id`, `zone_candidates` summary, `reason: Literal["cancelled", "timed_out"]`), published by `ResolvePendingZoneConfirmation` (cancel) and by a new `ExpirePendingZoneConfirmations` use case (timeout, run from the sweep job). `SerTicketNotificationTriggerHandler` gains `on_confirmation_dismissed`, gated behind a new preference-catalog row (e.g. `ser_zone_confirmation_dismissed`), rendering one template that branches on `reason` — mirrors `possibly_created`.

### D8: Supersession cancels silently; the confirmation-request message itself is (re)sent through the normal `SendNotification`/preferred-channel path with an `actions` extension
`NotificationMessage` gains an optional `actions: list[NotificationAction]` field (`label: str`, `callback_data: str`) that `NotificationChannelPort.send()` implementations may render as interactive buttons and otherwise ignore — keeping the port channel-agnostic in shape even though only `TelegramNotificationChannel` acts on `actions` today. When `SerTicketCreationTriggerHandler` detects a fresh ambiguous case for a vehicle that already has a `pending` row, it marks the old row `superseded` (no `SerZoneConfirmationDismissed`, no notification — the fresh request message is the only signal the owner needs) and sends a new confirmation request for the new candidates/location.

## Risks / Trade-offs

- **[Risk]** The vehicle sits unticketed for up to `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` while a confirmation is pending — a real fine-risk window, not just a UX delay. → Mitigation: default is short (10 min); it's the deliberate, explicit trade-off this change makes (asking beats silently guessing wrong), and the timeout notification tells the owner immediately so they can act manually.
- **[Risk]** An owner whose preferred channel isn't Telegram (once a second channel type exists) gets a confirmation request they have no way to answer, and it always times out. → Mitigation: fail-closed is the safe direction (no ticket, not a wrong one); flagged as a known limitation, not blocking this change since Telegram is the only channel today.
- **[Risk]** A tapped button for an already-superseded or already-resolved confirmation. → Mitigation: the webhook re-checks `status == "pending"` and `now < expires_at` before acting, and answers the callback with an explanatory alert either way — never a silent no-op from the user's perspective.
- **[Risk]** Spoofed callback tap — someone else guessing/replaying a `confirmation_id`. → Mitigation: `confirmation_id` is a random UUID (128 bits) and the webhook verifies the tapping `chat_id` matches the `user_id`'s configured Telegram `chat_id` before acting, not just that the row exists.
- **[Trade-off]** `SerTicketProviderPort.create_ticket()`'s signature changes for every current and future implementation. → Mitigation: the new parameter is optional and defaults to today's exact behavior; only `ElParkingSerTicketProvider` (the sole implementation) needs an actual code change.

## Migration Plan

1. Alembic migration: create `pending_zone_confirmations` (additive, no backfill, no existing-table changes) plus its two indexes.
2. Add the `ser_zone_confirmation_dismissed` row to the notification-types catalog (same migration pattern as prior notification-type additions) and its templates (all supported languages, per `notification_templates.py`'s coverage validation).
3. Add `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` (default `10`) to `config.py` and `.env.example`.
4. Ship code changes behind no feature flag — the new branch only activates when `find_all_containing()` returns more than one candidate for an `auto_create_ticket` owner, which is rare by construction (tight GPS tolerance, adjacent-zone frontier). Existing single-candidate behavior is provably unchanged (D1).
5. Rollback: revert the code changes and drop `pending_zone_confirmations` (and the new notification-type row) in a follow-up migration; nothing else in the schema depends on them.

## Open Questions

- Should a `PendingZoneConfirmation`'s candidate list cap at some N if more than two zones somehow overlap within tolerance (e.g. three-way frontier)? Telegram allows up to 100 buttons per keyboard so this isn't a hard limit yet, but worth a sanity cap during `tasks`.
- Exact wording/UX of the inline keyboard button labels (zone number + colour vs. zone number + neighbourhood) is a `tasks`-time detail, not a blocking design decision.
