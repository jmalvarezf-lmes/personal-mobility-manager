## 1. Domain layer

- [x] 1.1 Create `domain/entities/vehicle_ser_requirement_state.py` with `VehicleSerRequirementState` dataclass.
- [x] 1.2 Create `domain/events/ser_ticket_requirement_activated.py` with `SerTicketRequirementActivated` frozen dataclass.
- [x] 1.3 Create `domain/events/ser_ticket_requirement_deactivated.py` with `SerTicketRequirementDeactivated` frozen dataclass.
- [x] 1.4 Create `domain/value_objects/ser_ticket_requirement_deactivation_reason.py` with the `SerTicketRequirementDeactivationReason` enum (values: `left_zone`, `enforcement_inactive`, `ticket_active`, `exempt`).
- [x] 1.5 Create `domain/ports/vehicle_ser_requirement_state_repository.py` with `VehicleSerRequirementStateRepository` ABC.
- [x] 1.6 Create `domain/ports/user_ser_requirement_notification_repository.py` with `UserSerRequirementNotificationRepository` ABC.

## 2. Application layer

- [x] 2.1 Create `application/use_cases/evaluate_ser_ticket_requirement_state.py` implementing `EvaluateSerTicketRequirementState`.
- [x] 2.2 Implement inactive-state optimization using `SerZoneRecheckGate` and active-state full re-evaluation using `DetermineSerTicketRequirement`.
- [x] 2.3 Implement transition detection and event publishing for `SerTicketRequirementActivated` and `SerTicketRequirementDeactivated`.
- [x] 2.4 Create `application/event_handlers/ser_ticket_requirement_state_handler.py` as the `VehicleLocationUpdated` adapter that loads state, invokes the use case, and persists the result.
- [x] 2.5 Modify `application/event_handlers/ser_ticket_notification_trigger_handler.py` to subscribe to `SerTicketRequirementActivated` instead of `VehicleLocationUpdated`, and to record audit rows via `UserSerRequirementNotificationRepository` after successful sends.

## 3. Infrastructure layer

- [x] 3.1 Add `vehicle_ser_requirement_states` and `user_ser_requirement_notifications` tables to `infrastructure/orm/tables.py`.
- [x] 3.2 Create `infrastructure/repositories/postgres/vehicle_ser_requirement_state_repo.py` implementing `VehicleSerRequirementStateRepository`.
- [x] 3.3 Create `infrastructure/repositories/postgres/user_ser_requirement_notification_repo.py` implementing `UserSerRequirementNotificationRepository`.
- [x] 3.4 Generate Alembic migration for the new tables using `make db-revision msg="add ser requirement state and notification audit tables"`.

## 4. Presentation / wiring

- [x] 4.1 Wire `SerTicketRequirementStateHandler` and `EvaluateSerTicketRequirementState` in `presentation/api/app.py` lifespan.
- [x] 4.2 Subscribe `SerTicketRequirementStateHandler` to `VehicleLocationUpdated`.
- [x] 4.3 Repoint `SerTicketNotificationTriggerHandler` subscription from `VehicleLocationUpdated` to `SerTicketRequirementActivated`.
- [x] 4.4 Keep `SerTicketCreationTriggerHandler` subscribed to `VehicleLocationUpdated` unchanged.

## 5. Tests

- [x] 5.1 Add unit tests for `EvaluateSerTicketRequirementState` covering all transition scenarios (false→true, true→false, true→true, false→false) and deactivation reasons.
- [x] 5.2 Add unit tests for `SerTicketRequirementStateHandler`.
- [x] 5.3 Update `tests/application/event_handlers/test_ser_ticket_notification_trigger_handler.py` to use `SerTicketRequirementActivated` events and to assert audit repository calls.
- [x] 5.4 Add integration tests in `tests/infrastructure/` for the new Postgres repositories (skippable without `POSTGRES_DSN`).
- [x] 5.5 Run `make test` and `make lint` and fix any failures.

## 6. Documentation / validation

- [x] 6.1 Run `openspec validate --changes deduplicate-ser-ticket-required-notifications` and resolve any issues.
- [x] 6.2 Update `README.md` if any user-facing behavior or configuration changes (none expected for this change).
