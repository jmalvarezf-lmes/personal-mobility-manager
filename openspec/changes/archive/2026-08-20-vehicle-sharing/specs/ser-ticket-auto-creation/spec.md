## ADDED Requirements

### Requirement: Automatic SER ticket creation is scoped to the vehicle owner
When `SerTicketCreationTriggerHandler` creates an automatic SER ticket, it SHALL use the vehicle owner's `user_id` and the owner's connected SER provider configuration, regardless of any sharees. Sharees SHALL NOT trigger, authorize, or fund automatic ticket creation.

#### Scenario: Auto-creation uses owner user_id
- **WHEN** `SerTicketCreationTriggerHandler` calls `CreateSerTicket.execute`
- **THEN** the `user_id` argument is the vehicle's `owner_id`

#### Scenario: Sharee presence does not alter auto-creation behavior
- **WHEN** a vehicle has active sharees and a location event triggers auto-creation
- **THEN** the ticket is created using the owner's provider session and preferences
- **THEN** no sharee provider session is consulted
