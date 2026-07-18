## MODIFIED Requirements

### Requirement: DetermineSerTicketRequirement use case
The system SHALL implement a `DetermineSerTicketRequirement` application use case with `execute(zone: SerZone | None) -> bool`, returning whether a ticket is currently required for a vehicle located in `zone`. The use case SHALL accept an injected enforcement-schedule dependency (see the `ser-enforcement-schedule` capability's `SerEnforcementSchedule`) via its constructor, without changing `execute()`'s signature or any caller's call site — consistent with the seam reserved by the prior pure-presence-check implementation. `execute(zone)` SHALL return `False` immediately when `zone` is `None`, without consulting the injected dependency. When `zone` is not `None`, it SHALL return the result of calling the injected dependency's `is_active_now(zone.city_code)`. Home-proximity and resident-permit logic remain unevaluated seams for future changes.

#### Scenario: Ticket required when inside a zone during enforcement hours
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with a non-`None` `SerZone` and the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `True`
- **THEN** it returns `True`

#### Scenario: No ticket required when outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with `zone=None`
- **THEN** it returns `False`, without consulting the injected enforcement-schedule dependency

#### Scenario: No ticket required when inside a zone but outside enforcement hours
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with a non-`None` `SerZone` and the injected enforcement-schedule dependency's `is_active_now(zone.city_code)` returns `False` (e.g. it is a Sunday, a holiday, or outside today's operating hours)
- **THEN** it returns `False`

#### Scenario: Home-proximity and resident-permit logic remain unevaluated
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with a non-`None` `SerZone`
- **THEN** the result depends only on zone presence and the injected enforcement-schedule dependency's answer, since home-proximity and resident-permit factors are not wired in during this change
