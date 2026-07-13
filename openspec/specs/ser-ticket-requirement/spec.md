### Requirement: DetermineSerTicketRequirement use case
The system SHALL implement a `DetermineSerTicketRequirement` application use case with `execute(zone: SerZone | None) -> bool`, returning whether a ticket is currently required for a vehicle located in `zone`. This change's implementation SHALL be a pure presence check (`True` if `zone` is not `None`, `False` otherwise) — no enforcement-hours, home-proximity, or resident-permit logic is evaluated yet. This use case exists as the designated seam for those factors: each SHALL be added here as an injected dependency in a future change, without changing any caller's signature or call site.

#### Scenario: Ticket required when inside a zone
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with a non-`None` `SerZone`
- **THEN** it returns `True`

#### Scenario: No ticket required when outside all zones
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with `zone=None`
- **THEN** it returns `False`

#### Scenario: No time-of-day, home-proximity, or resident-permit logic is applied
- **WHEN** `DetermineSerTicketRequirement.execute(zone)` is called with a non-`None` `SerZone`, regardless of the current time or any vehicle/owner data
- **THEN** the result depends only on whether `zone` is `None`, since none of those factors are wired in during this change
