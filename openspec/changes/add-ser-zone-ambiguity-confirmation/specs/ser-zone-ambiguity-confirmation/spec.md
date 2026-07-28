## ADDED Requirements

### Requirement: PendingZoneConfirmation domain entity
The system SHALL define a `PendingZoneConfirmation` domain entity with fields: `id: UUID`, `vehicle_id: UUID`, `user_id: UUID`, `city_code: str`, `candidates: list[SerZoneCandidate]` (each carrying `zone_number`, `zone_type`, `district`; index `0` is always the primary zone `find_containing()` would have returned), `latitude: float`, `longitude: float`, `status: PendingZoneConfirmationStatus` (`PENDING`, `CONFIRMED`, `CANCELLED`, `TIMED_OUT`, `SUPERSEDED`), `created_at: datetime`, `expires_at: datetime`, `resolved_at: datetime | None`.

#### Scenario: Entity constructed with at least two candidates
- **WHEN** a `PendingZoneConfirmation` is constructed for an ambiguous location
- **THEN** `candidates` holds two or more `SerZoneCandidate` entries, with index `0` matching what `find_containing()` would return for the same location

---

### Requirement: pending_zone_confirmations table persists pending confirmations
The system SHALL create a `pending_zone_confirmations` table with columns: `id UUID PRIMARY KEY`, `vehicle_id UUID NOT NULL REFERENCES vehicles(id)`, `user_id UUID NOT NULL REFERENCES users(id)`, `city_code TEXT NOT NULL`, `candidates JSONB NOT NULL`, `latitude DOUBLE PRECISION NOT NULL`, `longitude DOUBLE PRECISION NOT NULL`, `status TEXT NOT NULL`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`, `expires_at TIMESTAMP WITH TIME ZONE NOT NULL`, `resolved_at TIMESTAMP WITH TIME ZONE`. A partial index SHALL exist on `vehicle_id` scoped to `status = 'pending'`, and a composite index SHALL exist on `(status, expires_at)`.

#### Scenario: Table schema
- **WHEN** the migration is applied
- **THEN** the `pending_zone_confirmations` table exists with all columns, the partial index on `(vehicle_id) WHERE status = 'pending'`, and the composite index on `(status, expires_at)`

---

### Requirement: PendingZoneConfirmationRepository port
The system SHALL define a `PendingZoneConfirmationRepository` port with: `save(confirmation: PendingZoneConfirmation) -> None` (insert or update by `id`), `find_by_id(confirmation_id: UUID) -> PendingZoneConfirmation | None`, `find_pending_for_vehicle(vehicle_id: UUID) -> PendingZoneConfirmation | None` (at most one row with `status = 'pending'` per vehicle by construction), `find_expired(now: datetime) -> list[PendingZoneConfirmation]` (all rows with `status = 'pending'` and `expires_at <= now`).

#### Scenario: At most one pending row per vehicle
- **WHEN** `find_pending_for_vehicle` is called for a vehicle with one row whose `status = 'pending'`
- **THEN** that row is returned; if no such row exists, `None` is returned

#### Scenario: find_expired returns only pending, past-deadline rows
- **WHEN** `find_expired(now)` is called
- **THEN** it returns every row with `status = 'pending'` and `expires_at <= now`, and no row with any other status

---

### Requirement: Configurable zone-confirmation timeout
The system SHALL expose a `get_ser_zone_confirmation_timeout_minutes() -> int` function in `config.py` that reads the `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` environment variable as an integer number of minutes, defaulting to `10` when unset or non-integer. This is a technical/operational setting, not a per-user preference, and is not exposed through any user-facing API.

#### Scenario: Default timeout applies when unset
- **WHEN** `SER_ZONE_CONFIRMATION_TIMEOUT_MINUTES` is not set in the environment
- **THEN** `get_ser_zone_confirmation_timeout_minutes()` returns `10`

---

### Requirement: SerTicketCreationTriggerHandler defers to a pending confirmation when the matched zone is ambiguous
When `SerTicketCreationTriggerHandler` resolves the SER zone containing the event's coordinates via `find_all_containing()` (see the modified `ser-zone-query` requirement) and `DetermineSerTicketRequirement.execute(candidates[0], ...)` returns `True`, if `len(candidates) > 1` the handler SHALL NOT call `CreateSerTicket.execute` directly. Instead it SHALL create a `PendingZoneConfirmation` (`status = PENDING`, `expires_at = now + get_ser_zone_confirmation_timeout_minutes()`, `candidates` populated from every matching zone, `latitude`/`longitude` from the event's coordinates) via `PendingZoneConfirmationRepository.save`, and send a notification to the owner's preferred channel whose `NotificationMessage.actions` contains one `NotificationAction` per candidate zone plus one Cancel action, each `callback_data` encoding `(confirmation.id, candidate_index | "x")`. If exactly one candidate matched, behavior is unchanged from the existing single-zone flow (`CreateSerTicket.execute` is called directly, no `PendingZoneConfirmation` is created).

#### Scenario: Ambiguous zone match creates a pending confirmation instead of a ticket
- **WHEN** a `VehicleLocationUpdated` event's coordinates match more than one SER zone within the configured containment tolerance, the owner has `auto_create_ticket = true`, and `DetermineSerTicketRequirement` returns `True` for the primary (first) matched zone
- **THEN** `CreateSerTicket.execute` is not called
- **THEN** a `PendingZoneConfirmation` is persisted with `status = PENDING`, one candidate per matched zone, and `expires_at` set `get_ser_zone_confirmation_timeout_minutes()` minutes in the future
- **THEN** a notification is sent to the owner's preferred channel with one action per candidate plus a Cancel action

#### Scenario: A single matching zone is unaffected
- **WHEN** a `VehicleLocationUpdated` event's coordinates match exactly one SER zone and `DetermineSerTicketRequirement` returns `True`
- **THEN** `CreateSerTicket.execute` is called directly, exactly as before this change, and no `PendingZoneConfirmation` is created

#### Scenario: A new pending confirmation supersedes an existing one for the same vehicle
- **WHEN** a `VehicleLocationUpdated` event would create a new `PendingZoneConfirmation` for a vehicle that already has one with `status = PENDING`
- **THEN** the existing row's `status` is set to `SUPERSEDED` without publishing `SerZoneConfirmationDismissed` and without sending any notification for it
- **THEN** a new `PendingZoneConfirmation` is created and its confirmation-request notification is sent

---

### Requirement: Telegram webhook resolves zone-confirmation button taps
`POST /notifications/telegram/webhook` SHALL, in addition to its existing `message`-based linking handling, branch on an incoming `callback_query` whose `data` matches the `zc:<confirmation_id_hex>:<candidate_index|x>` format. It SHALL look up the `PendingZoneConfirmation` by the decoded id, and SHALL only act if `status = PENDING`, `now < expires_at`, and the tapping update's `chat_id` matches the Telegram `NotificationRecipient` configured for the confirmation's `user_id`. If those checks pass, it SHALL call `ResolvePendingZoneConfirmation.execute(confirmation_id, chosen_index)` (`chosen_index = None` for Cancel). In every case — success, stale, expired, or chat mismatch — it SHALL call Telegram's `answerCallbackQuery` with an explanatory alert so the tapping user always sees a result, never a silent no-op.

#### Scenario: Valid tap on a candidate zone resolves the confirmation
- **WHEN** the webhook receives a `callback_query` with valid `zc:<id>:<index>` data for a `PENDING`, unexpired confirmation, from the chat linked to that confirmation's `user_id`
- **THEN** `ResolvePendingZoneConfirmation.execute` is called with that confirmation id and candidate index
- **THEN** `answerCallbackQuery` is called

#### Scenario: Tap on Cancel resolves the confirmation with no chosen zone
- **WHEN** the webhook receives a `callback_query` with `zc:<id>:x` data for a `PENDING`, unexpired confirmation
- **THEN** `ResolvePendingZoneConfirmation.execute` is called with `chosen_index = None`

#### Scenario: Tap on an already-resolved or expired confirmation is rejected without acting
- **WHEN** the webhook receives a `callback_query` referencing a confirmation whose `status` is no longer `PENDING`, or whose `expires_at` has already passed
- **THEN** `ResolvePendingZoneConfirmation.execute` is not called
- **THEN** `answerCallbackQuery` is still called, with an alert explaining the confirmation is no longer valid

#### Scenario: Tap from a chat that doesn't match the confirmation's owner is rejected
- **WHEN** the webhook receives a `callback_query` whose `chat_id` does not match the Telegram recipient configured for the confirmation's `user_id`
- **THEN** `ResolvePendingZoneConfirmation.execute` is not called

---

### Requirement: ResolvePendingZoneConfirmation use case creates the confirmed ticket or dismisses the confirmation
The system SHALL define a `ResolvePendingZoneConfirmation` use case with `execute(confirmation_id: UUID, chosen_index: int | None) -> None`. When `chosen_index` is not `None`, it SHALL resolve the owner's first connected SER ticket provider and `default_ticket_duration_minutes` exactly as `SerTicketCreationTriggerHandler` does today, call `CreateSerTicket.execute(..., location=GeoLocation(lat=confirmation.latitude, lng=confirmation.longitude), zone=candidates[chosen_index])`, mark the confirmation `CONFIRMED`, and publish `SerTicketCreated` on success or `SerTicketCreationFailed` on any exception — the same events `SerTicketCreationTriggerHandler` publishes for a direct creation. When `chosen_index` is `None` (Cancel), it SHALL mark the confirmation `CANCELLED` and publish `SerZoneConfirmationDismissed` with `reason = "cancelled"`.

#### Scenario: Confirming a candidate creates a ticket for that exact zone
- **WHEN** `ResolvePendingZoneConfirmation.execute(confirmation_id, chosen_index)` is called for a `PENDING` confirmation
- **THEN** `CreateSerTicket.execute` is called with `zone` set to `candidates[chosen_index]`, not a fresh `find_containing()` resolution
- **THEN** the confirmation's `status` becomes `CONFIRMED` and `SerTicketCreated` is published on success

#### Scenario: Cancelling publishes a dismissal with no ticket created
- **WHEN** `ResolvePendingZoneConfirmation.execute(confirmation_id, None)` is called for a `PENDING` confirmation
- **THEN** `CreateSerTicket.execute` is not called
- **THEN** the confirmation's `status` becomes `CANCELLED` and `SerZoneConfirmationDismissed` is published with `reason = "cancelled"`

---

### Requirement: ExpirePendingZoneConfirmations use case and scheduled sweep
The system SHALL define an `ExpirePendingZoneConfirmations` use case that finds every `PendingZoneConfirmation` via `PendingZoneConfirmationRepository.find_expired(now)`, marks each `status = TIMED_OUT`, and publishes `SerZoneConfirmationDismissed` with `reason = "timed_out"` for each. A scheduler (same `BackgroundScheduler` "interval" pattern as `SessionCleanupScheduler`) SHALL run this use case on a fixed short interval (on the order of one minute, distinct from `SessionCleanupScheduler`'s interval) so an unanswered confirmation is noticed close to its `expires_at`.

#### Scenario: An unanswered confirmation past its deadline is expired
- **WHEN** the sweep runs and a `PendingZoneConfirmation` has `status = PENDING` and `expires_at` in the past
- **THEN** its `status` becomes `TIMED_OUT` and `SerZoneConfirmationDismissed` is published with `reason = "timed_out"`

#### Scenario: A confirmation still within its deadline is left untouched
- **WHEN** the sweep runs and a `PendingZoneConfirmation` has `status = PENDING` and `expires_at` in the future
- **THEN** it is not modified and no event is published for it

---

### Requirement: Owner is notified when a confirmation is dismissed without a ticket
When `SerZoneConfirmationDismissed` is published, `SerTicketNotificationTriggerHandler` SHALL look up the owner's `ser_zone_confirmation_dismissed` notification preference; if the row is missing or `enabled=false`, it SHALL skip silently. Otherwise it SHALL render one localized message stating no SER ticket was created, branching its wording on `event.reason` (`"cancelled"` vs `"timed_out"`) the same way `on_ticket_creation_failed` branches on `possibly_created`, and call `SendNotification.execute`.

#### Scenario: Cancellation is reported to the owner
- **WHEN** `SerZoneConfirmationDismissed` is published with `reason = "cancelled"` and the owner's preference is enabled
- **THEN** `SendNotification.execute` is called with a message reflecting that the owner cancelled and no ticket was created

#### Scenario: Timeout is reported to the owner
- **WHEN** `SerZoneConfirmationDismissed` is published with `reason = "timed_out"` and the owner's preference is enabled
- **THEN** `SendNotification.execute` is called with a message reflecting that no answer was received in time and no ticket was created

#### Scenario: Disabled preference skips the notification
- **WHEN** `SerZoneConfirmationDismissed` is published and the owner's `ser_zone_confirmation_dismissed` preference is missing or disabled
- **THEN** `SendNotification.execute` is not called
