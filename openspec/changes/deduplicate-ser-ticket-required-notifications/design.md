## Context

See `proposal.md` for the motivation. The current event pipeline publishes a `VehicleLocationUpdated` event on every location poll, even when coordinates are unchanged. `SerTicketNotificationTriggerHandler` subscribes directly to that event and sends a `ser_zone_ticket_required` notification whenever `DetermineSerTicketRequirement.execute` returns `true`. Because `SerZoneRecheckGate` intentionally rechecks stationary vehicles that hold no active ticket, a parked vehicle in an enforcement-active zone produces a notification every poll cycle.

The existing `ser_ticket_created` and `ser_ticket_creation_failed` notification paths are event-driven and one-shot; only the `ser_zone_ticket_required` path is recurring. This design keeps creation on `VehicleLocationUpdated` and moves only the notification trigger to a new `SerTicketRequirementActivated` event.

## Goals / Non-Goals

**Goals:**
- Model the SER ticket requirement as a per-vehicle state with `RequirementActive` / `NoRequirement` episodes.
- Emit `SerTicketRequirementActivated` exactly when the stored state transitions from inactive to active.
- Move `SerTicketNotificationTriggerHandler` so it reacts to `SerTicketRequirementActivated` instead of `VehicleLocationUpdated`.
- Provide a durable audit record of who was notified about each activation.
- Keep the change minimal enough that existing tests for `SerTicketCreationTriggerHandler` continue to pass with little or no modification.

**Non-Goals:**
- Changing the behavior of automatic ticket creation, including its retry semantics.
- Building a generic notification history or delivery log.
- Changing notification preferences, templates, or channels.
- Adding an "all clear" notification on deactivation.
- Supporting catch-up notifications for users who enable the preference or are added as sharees while a requirement is already active.

## Decisions

### 1. State machine instead of similarity/cooldown
A state machine tracks the *transition* of the underlying requirement, which is the real event of interest. Similarity-based deduplication ("same position, same zone") or a fixed cooldown would be simpler but would obscure the domain rule and behave incorrectly across enforcement schedule boundaries.

### 2. Variant D2: only notification moves to the activation event
`SerTicketCreationTriggerHandler` stays subscribed to `VehicleLocationUpdated`. This preserves its existing retry behavior when ticket creation fails; moving creation to the activation event would require adding a separate retry mechanism.

### 3. One state row per vehicle
A vehicle has exactly one current location and therefore one current requirement at a time. One row in `vehicle_ser_requirement_states` is sufficient. When the vehicle moves away and later returns, a new episode begins naturally.

### 4. Use case owns transition logic
The transition logic lives in `EvaluateSerTicketRequirementState`, an application-layer use case. The event handler `SerTicketRequirementStateHandler` is a thin adapter that loads the existing state, invokes the use case, and persists the returned state. This mirrors the existing pattern where `CreateSerTicket` is a use case and `SerTicketCreationTriggerHandler` is its event adapter.

### 5. Per-user audit table
`user_ser_requirement_notifications` records which user was notified for which activation event. It is not a generic notification log; it is scoped to SER requirement activations so it can answer "was this user already told about the current active episode?" if that question becomes needed later.

### 6. Emit deactivation event with no current consumer
`SerTicketRequirementDeactivated` is published even though no handler currently subscribes to it. This matches the project's existing style of publishing domain events that may be consumed later, keeps the state machine symmetric, and avoids a future consumer having to infer deactivation from the absence of activation events.

### 7. Always re-evaluate when state is active
When `VehicleSerRequirementState.is_required` is `true`, `EvaluateSerTicketRequirementState` always calls `DetermineSerTicketRequirement.execute`. This is necessary to reliably detect deactivation when a ticket is created or enforcement ends. When `is_required` is `false`, it uses `SerZoneRecheckGate` to avoid unnecessary zone lookups.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| More frequent `DetermineSerTicketRequirement` calls while state is active | Acceptable: correctness requires re-evaluation; the call is cheap relative to the downstream notification or ticket creation it prevents. |
| One extra notification on first deploy for already-active requirements | Acceptable per user confirmation. Existing vehicles will emit one activation event on the first poll after deploy, then stop repeating. |
| Push events racing with pull events | The state repository update is a single-row upsert per vehicle; the last write wins and the requirement computation is idempotent. |
| Audit write failure should not lose or repeat the notification | Audit is written after notification; failures are logged and swallowed. |
| New sharee or re-enabled preference mid-episode gets no notification | Documented non-goal; user will be notified on the next activation episode. |

## Migration Plan

1. Run the new Alembic revision to create `vehicle_ser_requirement_states` and `user_ser_requirement_notifications`.
2. Deploy the application. No data backfill is required.
3. On the first `VehicleLocationUpdated` after deploy for each vehicle, state will be initialized and an activation event will be emitted if the requirement is currently active. This may produce one additional notification per active vehicle.
4. Rollback: revert the deployment and, if desired, drop the two new tables via a down migration.

## Open Questions

None remaining. All material design decisions were resolved during exploration.
