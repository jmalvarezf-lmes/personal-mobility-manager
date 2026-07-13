## Why

`SerTicketTriggerHandler` has been a deliberate no-op scaffold since `add-vehicle-location-notification`, registered against `VehicleLocationUpdated` specifically so this behavior could be widened later without touching the wiring. This change activates it: when a vehicle's location changes meaningfully (reusing the same previous-location/threshold check `NotificationDispatchHandler` already uses), the handler checks whether the new location falls inside a SER zone and, if a ticket is currently required, notifies the owner via their preferred channel that a SER ticket must be created. Automatic ticket creation is explicitly out of scope for this change — this only notifies.

## What Changes

- Activate `SerTicketTriggerHandler`: on `VehicleLocationUpdated`, look up the vehicle's previous recorded location and compute the distance moved, using the same `distance_m` + `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` logic `NotificationDispatchHandler` already applies. If the location is unchanged (below threshold) relative to the previous ping, skip — do not re-check or re-notify. Otherwise (including the vehicle's first-ever recorded location), check zone containment.
- Add `DetermineSerTicketRequirement`, a new application use case that takes the `SerZone | None` result of `FindContainingSerZone` and returns whether a ticket is required right now. Today this is a pure presence check (`zone is not None`). It exists as its own use case — not a bare domain function — because it is the designated seam for factors that don't exist yet: proximity to the vehicle owner's home address (resident exemption), a resident permit held for that specific zone, and zone enforcement hours/timetable. Each of those will be added here as an injected dependency in a future change, without changing any caller.
- When `DetermineSerTicketRequirement` returns `True`, look up the owner's preferences and render a new localized notification ("a SER ticket must be created for this location") in `en`/`es`, then dispatch it via the existing `SendNotification` use case (preferred channel, no fan-out — unchanged from how movement notifications are sent).
- No new domain event, no new event-publisher subscription: this reuses `SerTicketTriggerHandler`'s existing registration against `VehicleLocationUpdated`.
- No ticket is created. No provider is called. This change is notification-only, matching the pattern already used to gradually widen this handler.
- No SER zone enforcement-hours/timetable data is introduced in this change — the notification fires regardless of time of day. This is a known, accepted limitation for this slice, not an oversight.

## Capabilities

### New Capabilities
- `ser-ticket-requirement`: the `DetermineSerTicketRequirement` use case — the extensible seam that decides whether a ticket is currently required for a given SER zone containment result.
- `ser-zone-ticket-notification`: the activated `SerTicketTriggerHandler` behavior — reusing the movement-threshold check, calling `FindContainingSerZone` and `DetermineSerTicketRequirement`, and sending the localized notification.

### Modified Capabilities
- `vehicle-location-events`: the "SerTicketTriggerHandler is registered but inert" requirement is replaced — the handler now performs real SER zone lookups and may trigger a notification.
- `notification-channel`: adds a new notification template key/content for the SER-ticket-required message, in `en` and `es`.

## Impact

- **Backend**: `application/event_handlers/ser_ticket_trigger_handler.py` (now real), new `application/use_cases/determine_ser_ticket_requirement.py`, `application/notification_templates.py` (new template key), no changes to DI wiring in `app.py` beyond what's already registered (handler is already subscribed).
- **No new migrations, tables, or config**: reuses `FindContainingSerZone`, `SendNotification`, `VehicleLocationRepository.get_previous`, and the existing `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var — no new environment variables introduced.
- **No frontend changes.**
- **No changes** to automatic ticket creation (still out of scope), to enforcement-hours/timetable data (still absent), or to any notification channel implementation.
