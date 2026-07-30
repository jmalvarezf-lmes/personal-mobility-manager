## Why

A stationary vehicle can become subject to a SER ticket purely from the passage of time — enforcement-schedule activation, or an existing ticket's expiry — with zero GPS movement. Today nothing re-evaluates that: `RecordVehicleLocation` discards any location ping whose coordinates exactly match the last stored fix, so once a polled vehicle (default every 5 minutes) sits still, no `VehicleLocationUpdated` event is published again until it actually moves — the SER handlers never get a chance to run. Separately, the two SER handlers (`SerTicketCreationTriggerHandler`, `SerTicketNotificationTriggerHandler`) each duplicate near-identical previous-location/distance/zone-comparison plumbing, which is starting to be hard to keep in sync as this logic grows.

## What Changes

- `RecordVehicleLocation` no longer discards a ping whose coordinates are unchanged from the last stored location: it still skips writing a duplicate `VehicleLocation` row, but always publishes `VehicleLocationUpdated` (with a fresh `received_at`), so every poll cycle still gives SER-related handlers a chance to re-evaluate.
- A new shared collaborator, `SerZoneRecheckGate`, centralizes the "is this ping worth acting on" decision for both SER handlers: if the vehicle currently holds no active `ParkingTicket`, it always signals a recheck (time-based state changes must not be missed); if it does hold one, it applies the existing movement-floor and zone-unchanged optimizations (unified across both callers — today only the creation handler has the zone-unchanged check, the notification handler will gain it too) before allowing a skip.
- `SerTicketCreationTriggerHandler` and `SerTicketNotificationTriggerHandler` both replace their inline previous-location/distance/zone-comparison logic with a call to `SerZoneRecheckGate`, each still passing their own independent movement floor (the fixed technical floor for creation, the per-user configurable threshold for notification — these remain two separate values, never shared).

## Capabilities

### New Capabilities
- `ser-zone-recheck-gate`: Shared decision logic for whether a `VehicleLocationUpdated` event should proceed to a SER zone/requirement check, gating the existing movement/zone-unchanged skip behind whether the vehicle currently holds any active `ParkingTicket`.

### Modified Capabilities
- `vehicle-location-events`: `RecordVehicleLocation` now always publishes `VehicleLocationUpdated` for a validated location, even when it matches the previously stored location exactly (it only skips the redundant persistence, not the event).
- `ser-ticket-auto-creation`: `SerTicketCreationTriggerHandler`'s skip-on-insufficient-movement logic is now delegated to `SerZoneRecheckGate`, and no longer skips when the vehicle holds no active ticket regardless of movement/zone-unchanged.
- `ser-zone-ticket-notification`: `SerTicketNotificationTriggerHandler`'s skip-on-insufficient-movement logic is now delegated to the same `SerZoneRecheckGate`, gaining the zone-unchanged optimization it previously lacked, and no longer skips when the vehicle holds no active ticket.

## Impact

- `src/mobility_manager/application/use_cases/record_vehicle_location.py` — remove the early-return discard; keep the no-duplicate-row persistence check.
- `src/mobility_manager/application/use_cases/ser_zone_recheck_gate.py` (new) — the shared collaborator.
- `src/mobility_manager/application/event_handlers/ser_ticket_creation_trigger_handler.py` — replace inline logic with a call to the new gate.
- `src/mobility_manager/application/event_handlers/ser_ticket_notification_trigger_handler.py` — same.
- `src/mobility_manager/presentation/api/factories.py` (or wherever handlers are wired) — construct and inject `SerZoneRecheckGate` into both handlers.
- Downstream `VehicleLocationUpdated` subscribers (`NotificationDispatchHandler`) are unaffected: they already no-op on zero/near-zero distance, so the extra "unchanged" events they now receive change nothing about their behavior.
- Minor added cost: one extra `ParkingTicketRepository.find_all_active_for_vehicle` call per stationary poll per vehicle (already a cheap, indexed, existing query pattern).
