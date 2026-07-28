## 1. Config

- [ ] 1.1 Add `get_ser_zone_confirmation_timeout_minutes() -> int` to `src/mobility_manager/config.py`, reading `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` with int-with-fallback (default `10`), mirroring `get_ser_zone_containment_tolerance_cm()`'s style.
- [ ] 1.2 Add `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES=10` to `.env.example` with a one-line comment.

## 2. Migration

- [ ] 2.1 Add an Alembic migration creating `pending_zone_confirmations`: `id UUID PRIMARY KEY`, `vehicle_id UUID NOT NULL REFERENCES vehicles(id)`, `user_id UUID NOT NULL REFERENCES users(id)`, `city_code TEXT NOT NULL`, `candidates JSONB NOT NULL`, `latitude DOUBLE PRECISION NOT NULL`, `longitude DOUBLE PRECISION NOT NULL`, `status TEXT NOT NULL`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`, `expires_at TIMESTAMP WITH TIME ZONE NOT NULL`, `resolved_at TIMESTAMP WITH TIME ZONE`.
- [ ] 2.2 In the same migration, add a partial index on `vehicle_id WHERE status = 'pending'` and a composite index on `(status, expires_at)`.
- [ ] 2.3 Add a migration inserting the `ser_zone_confirmation_dismissed` row into the `notification_types` catalog, following the pattern of `911464896d6c_add_ser_ticket_creation_notification_types.py`.

## 3. Domain

- [ ] 3.1 Add `SerZoneCandidate` value object (`zone_number: str`, `zone_type: str`, `district: str`) to `src/mobility_manager/domain/value_objects/`.
- [ ] 3.2 Add `PendingZoneConfirmationStatus` enum (`PENDING`, `CONFIRMED`, `CANCELLED`, `TIMED_OUT`, `SUPERSEDED`) and `PendingZoneConfirmation` entity (fields per design.md D3) to `src/mobility_manager/domain/entities/`.
- [ ] 3.3 Add `PendingZoneConfirmationRepository` abstract port (`save`, `find_by_id`, `find_pending_for_vehicle`, `find_expired`) to `src/mobility_manager/domain/ports/`.
- [ ] 3.4 Add `find_all_containing(location: GeoLocation) -> list[SerZone]` to `SerZoneRepository` port in `src/mobility_manager/domain/ports/ser_zone_repository.py`.
- [ ] 3.5 Add `NotificationAction` value object (`label: str`, `callback_data: str`) to `src/mobility_manager/domain/value_objects/notification_message.py`, and add `actions: list[NotificationAction] | None = None` to `NotificationMessage`.
- [ ] 3.6 Add `SerZoneConfirmationDismissed` domain event (`vehicle_id`, `user_id`, `reason: Literal["cancelled", "timed_out"]`) to `src/mobility_manager/domain/events/`.
- [ ] 3.7 Add `zone: SerZone | None = None` parameter to `SerTicketProviderPort.create_ticket()` in `src/mobility_manager/domain/ports/ser_ticket_provider.py`, updating its docstring per the modified `ser-ticket-provider` spec.

## 4. Infrastructure — SER zone repository

- [ ] 4.1 Implement `PostgresSerZoneRepository.find_all_containing()`, reusing the same tolerance-aware `zone.contains()` loop `find_containing()` uses today but collecting every match instead of returning on the first.
- [ ] 4.2 Reimplement `find_containing()` as `find_all_containing(location)[0] if candidates else None`, removing the now-duplicated loop.
- [ ] 4.3 Implement `FindContainingSerZone`'s sibling use case, or extend it, so the ambiguity-detection call site (`SerTicketCreationTriggerHandler`) can obtain the full candidate list — add `find_containing_ser_zone.execute_all(location) -> list[SerZone]` (or a small new `FindAllContainingSerZones` use case, matching the existing one-use-case-per-repo-method convention) in `src/mobility_manager/application/use_cases/`.

## 5. Infrastructure — PendingZoneConfirmation persistence

- [ ] 5.1 Implement `PostgresPendingZoneConfirmationRepository` in `src/mobility_manager/infrastructure/repositories/postgres/`, serializing `candidates` to/from the `JSONB` column.
- [ ] 5.2 Add the `pending_zone_confirmations` SQLAlchemy Core table definition to `src/mobility_manager/infrastructure/orm/tables.py`.

## 6. Infrastructure — provider zone override

- [ ] 6.1 Update `ElParkingSerTicketProvider.create_ticket()` in `src/mobility_manager/infrastructure/ser_ticket_providers/elparking/provider.py`: `ser_zone = zone or self._ser_zone_repo.find_containing(location)`, per design.md D5.
- [ ] 6.2 Add `zone: SerZone | None = None` to `CreateSerTicket.execute()` in `src/mobility_manager/application/use_cases/create_ser_ticket.py`, forwarded unchanged to `provider.create_ticket(...)`.

## 7. Application — confirmation lifecycle use cases

- [ ] 7.1 Extract the provider-resolution + duration-resolution + `CreateSerTicket.execute` + event-publishing logic currently inline in `SerTicketCreationTriggerHandler._create_ticket` into a small shared helper (module-level function or injected collaborator) callable from both that handler and the new use case below, per design.md D6.
- [ ] 7.2 Implement `ResolvePendingZoneConfirmation` use case (`application/use_cases/resolve_pending_zone_confirmation.py`): loads the confirmation, on `chosen_index is not None` calls the shared ticket-creation helper with `zone=candidates[chosen_index]` and marks `CONFIRMED`, publishing `SerTicketCreated`/`SerTicketCreationFailed`; on `chosen_index is None` marks `CANCELLED` and publishes `SerZoneConfirmationDismissed(reason="cancelled")`.
- [ ] 7.3 Implement `ExpirePendingZoneConfirmations` use case (`application/use_cases/expire_pending_zone_confirmations.py`): finds expired rows via `find_expired(now)`, marks each `TIMED_OUT`, publishes `SerZoneConfirmationDismissed(reason="timed_out")` per row.

## 8. Application — event handler changes

- [ ] 8.1 Update `SerTicketCreationTriggerHandler.handle()` in `src/mobility_manager/application/event_handlers/ser_ticket_creation_trigger_handler.py` to call the new all-candidates lookup (task 4.3) instead of `FindContainingSerZone.execute`, run `DetermineSerTicketRequirement` against `candidates[0]`, and branch: `len(candidates) == 1` → existing direct-creation path unchanged; `len(candidates) > 1` → new ambiguity path.
- [ ] 8.2 Implement the ambiguity path: supersede any existing `PENDING` row for the vehicle (`status = SUPERSEDED`, no event, no notification — design.md D8), create and save a new `PendingZoneConfirmation` (`expires_at = now + get_ser_zone_confirmation_timeout_minutes()`), build one `NotificationAction` per candidate (`callback_data = f"zc:{confirmation.id.hex}:{index}"`) plus a Cancel action (`callback_data = f"zc:{confirmation.id.hex}:x"`), render the confirmation-request message, and call `SendNotification.execute`.
- [ ] 8.3 Add the `ser_zone_confirmation_requested` template directory (`application/templates/ser_zone_confirmation_requested/<lang>.txt.j2`, one file per language in `SUPPORTED_LANGUAGES`) listing the candidate zones (number + type) and explaining the buttons.
- [ ] 8.4 Add the `ser_zone_confirmation_dismissed` template directory (one file per language), branching wording on a `reason` template variable (`"cancelled"` vs `"timed_out"`), mirroring `ser_ticket_creation_failed`'s `possibly_created` pattern.
- [ ] 8.5 Add `on_confirmation_dismissed(event: SerZoneConfirmationDismissed)` to `SerTicketNotificationTriggerHandler`: preference-gated on `ser_zone_confirmation_dismissed`, renders the template from 8.4, calls `SendNotification.execute`. Wrap in the same broad try/except + root trace span convention as its sibling methods.
- [ ] 8.6 Subscribe `on_confirmation_dismissed` to `SerZoneConfirmationDismissed` at event-publisher wiring time (`presentation/api/app.py` or wherever handlers are currently subscribed).

## 9. Infrastructure — Telegram inline keyboard + webhook callback handling

- [ ] 9.1 Update `TelegramNotificationChannel._send_message` (or add a sibling) to include `reply_markup: {"inline_keyboard": [[{"text": label, "callback_data": data}], ...]}` in the `sendMessage` body when `message.actions` is set.
- [ ] 9.2 Add an `answer_callback_query(callback_query_id: str, text: str | None = None, show_alert: bool = False) -> None` method to `TelegramNotificationChannel` (or a small dedicated helper), calling Telegram's `answerCallbackQuery` endpoint.
- [ ] 9.3 In `presentation/api/routers/notifications.py`'s `telegram_webhook`, branch on `update.get("callback_query")`: parse `zc:<hex>:<index|x>` from `callback_query["data"]`, resolve the `PendingZoneConfirmationRepository`, validate `status == PENDING`, `now < expires_at`, and that `callback_query["message"]["chat"]["id"]` matches the Telegram recipient configured for the confirmation's `user_id`. On success call `ResolvePendingZoneConfirmation.execute(...)`; in every branch (success, stale, expired, chat mismatch, malformed data) call `answer_callback_query` with an explanatory message.
- [ ] 9.4 Guard the existing `message`-only linking logic so it is not reached for a `callback_query` update (early return after handling `callback_query`).

## 10. Infrastructure — expiry sweep scheduler

- [ ] 10.1 Add `PendingZoneConfirmationExpiryScheduler` to `src/mobility_manager/infrastructure/scheduler.py`, mirroring `SessionCleanupScheduler`'s `BackgroundScheduler` "interval" + try/except-never-raises pattern, calling `ExpirePendingZoneConfirmations.execute()` on a short (minutes-scale) interval distinct from `SessionCleanupScheduler`'s.
- [ ] 10.2 Wire the new scheduler's `start()`/`stop()` into `presentation/api/app.py`'s lifespan, alongside the existing schedulers.

## 11. Wiring

- [ ] 11.1 Register `PostgresPendingZoneConfirmationRepository`, `ResolvePendingZoneConfirmation`, `ExpirePendingZoneConfirmations`, and the new use case from task 4.3 on `app.state` in `presentation/api/app.py`, following the existing construction/injection pattern for sibling use cases.
- [ ] 11.2 Pass the new repository/use cases into `SerTicketCreationTriggerHandler`'s and `SerTicketNotificationTriggerHandler`'s constructors where needed, updating their registration at startup.

## 12. Tests — Domain (unit)

- [ ] 12.1 `tests/domain/entities/test_pending_zone_confirmation.py`: construction, status transitions.
- [ ] 12.2 `tests/domain/value_objects/test_notification_message.py` (or extend existing): `actions` defaults to `None`, round-trips when given.

## 13. Tests — Application (unit, mocked ports)

- [ ] 13.1 `tests/application/test_find_containing_ser_zone.py` (or new file): the all-candidates use case returns every tolerance-matching zone; empty list when none match.
- [ ] 13.2 `tests/application/event_handlers/test_ser_ticket_creation_trigger_handler.py`: single-candidate path unchanged (regression); ambiguous path creates a `PendingZoneConfirmation` and sends a notification with the right actions instead of calling `CreateSerTicket`; a fresh ambiguous event supersedes an existing pending row without a dismissal event.
- [ ] 13.3 `tests/application/use_cases/test_resolve_pending_zone_confirmation.py`: confirm path calls `CreateSerTicket.execute` with the chosen candidate as `zone` and publishes `SerTicketCreated`; cancel path publishes `SerZoneConfirmationDismissed(reason="cancelled")` without calling `CreateSerTicket`; provider failure on confirm publishes `SerTicketCreationFailed`.
- [ ] 13.4 `tests/application/use_cases/test_expire_pending_zone_confirmations.py`: expired rows are marked `TIMED_OUT` and dismissed with `reason="timed_out"`; non-expired rows are untouched.
- [ ] 13.5 `tests/application/use_cases/test_create_ser_ticket.py`: an explicit `zone` argument is forwarded to the provider unchanged (regression: omitted `zone` behaves exactly as before).
- [ ] 13.6 `tests/application/event_handlers/test_ser_ticket_notification_trigger_handler.py`: `on_confirmation_dismissed` respects the `ser_zone_confirmation_dismissed` preference gate and branches wording on `reason`.
- [ ] 13.7 `tests/application/test_notification_templates.py`: `ser_zone_confirmation_requested` and `ser_zone_confirmation_dismissed` have full language coverage (covered automatically by `validate_language_coverage` at import time, but add explicit render tests for both).

## 14. Tests — Infrastructure (integration, requires POSTGRES_DSN)

- [ ] 14.1 `tests/infrastructure/test_ser_zone_repo_integration.py`: `find_all_containing()` returns multiple zones for a location within tolerance of two adjacent stored polygons; `find_containing()` still returns only the first.
- [ ] 14.2 `tests/infrastructure/repositories/test_pending_zone_confirmation_repo.py` (integration): save/find_by_id round-trip; `find_pending_for_vehicle` returns at most one row; `find_expired` filters correctly by status and `expires_at`.
- [ ] 14.3 `tests/infrastructure/test_telegram_notification_channel.py`: `send()` includes `reply_markup` when `actions` is set and omits it otherwise; `answer_callback_query` calls the right endpoint.

## 15. Tests — Presentation (e2e, TestClient)

- [ ] 15.1 `tests/presentation/test_notifications_router.py`: a valid `callback_query` confirming a candidate resolves the confirmation and returns `{"ok": True}`; a stale/expired/chat-mismatched `callback_query` is rejected without side effects; `message`-based linking still works unaffected by the new branch.

## 16. Consistency checks

- [ ] 16.1 Update `README.md`'s environment-variables section with `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` (per this repo's mandatory README-consistency rule).
- [ ] 16.2 Confirm no `Makefile` target needs a new step (this change adds no new build/test/lint command) — if one does turn out to be needed while implementing, update the `Makefile` in the same commit.

## 17. Verification

- [ ] 17.1 Run `make test` and confirm all non-integration tests pass.
- [ ] 17.2 Run `make coverage` and confirm `domain/` stays at 100% and `application/` stays at or above 80%.
- [ ] 17.3 Manually verify end-to-end against a real Telegram bot: trigger an ambiguous zone match for an `auto_create_ticket` test vehicle, confirm the inline keyboard arrives, tap a candidate, confirm a ticket is created for that exact zone; separately confirm Cancel and a timeout both result in no ticket and a dismissal notification.
