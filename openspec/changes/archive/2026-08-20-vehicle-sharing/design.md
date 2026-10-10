## Context

See `proposal.md` for motivation. The codebase currently models a vehicle with a single `user_id` field that implicitly denotes the owner. All authenticated vehicle endpoints enforce `vehicle.user_id == current_user.id`, and all vehicle notifications are sent to that single user. This design renames that field to `owner_id`, introduces a `VehicleShare` relationship, and splits authorization into "access" (read + notifications) versus "owner" (write + delete).

## Goals / Non-Goals

**Goals:**
- Make ownership explicit via `Vehicle.owner_id` and a new `VehicleShare` entity.
- Allow owners to share a vehicle with any registered user by email, immediately and idempotently.
- Let sharees view the vehicle, its location history, SER ticket history, and SER parking exemption.
- Keep all write/destructive operations owner-only.
- Redact brand-specific credentials from sharee views without breaking the existing frontend shape.
- Fan out notifications to sharees based on each sharee's own notification preferences.
- Preserve Clean Architecture layer boundaries (domain has no framework/ORM imports, presentation depends only on application/use cases).

**Non-Goals:**
- Invitation flows for users not yet on the platform.
- Transferring vehicle ownership.
- Fine-grained roles beyond owner/sharee.
- Showing the owner's identity to sharees in this iteration.
- Separate notification preference defaults for sharees.

## Decisions

### D1: Rename `Vehicle.user_id` to `Vehicle.owner_id`
**Rationale:** The field already meant "creator/owner"; renaming makes the semantics explicit and leaves no ambiguity once sharees exist. This is Option B from exploration.
**Alternative considered:** Keep `user_id` and add `owner_id` as a separate column. Rejected because it leaves a deprecated column and two sources of truth.
**Impact:** Alembic migration renames the column; every query, use case, test fixture, and event handler referencing `vehicle.user_id` must be updated.

### D2: New `vehicle_shares` table with composite PK `(vehicle_id, user_id)`
**Rationale:** A vehicle can have many sharees; a user can be shared on many vehicles. The composite key prevents duplicates naturally.
**Schema:**
```sql
vehicle_shares (
  vehicle_id UUID REFERENCES vehicles(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (vehicle_id, user_id)
)
```
**Impact:** Deleting a vehicle or a user cascades away their share rows automatically.

### D3: Add case-insensitive `find_by_email` to `UserRepository`
**Rationale:** The share endpoint accepts an email and must resolve it to a `User` id. The port previously lacked email lookup. A case-insensitive lookup avoids user-visible failures due to address casing, and a unique case-insensitive index guarantees no duplicate accounts can be created with differently-cased versions of the same address.
**Impact:** Domain port gets `find_by_email(email: str) -> User | None`; Postgres implementation matches on `lower(email)` using a unique functional index `unique_lower_email` on `users.email`.

### D4: Two authorization primitives
**Rationale:** FastAPI resolves `Depends()` before body parsing, so routes with bodies must keep the inline check pattern already used in this codebase. Splitting into two functions keeps the existing body-then-auth ordering while making the role distinction clear.
- `require_vehicle_access(request, vehicle_id, current_user) -> VehicleAccess`: used by read endpoints (owner or sharee).
- `require_vehicle_owner(request, vehicle_id, current_user) -> Vehicle`: used inside write endpoints after body parsing.
**Alternative considered:** A single `Depends` that returns access level. Rejected because it would reintroduce the body-vs-auth ordering problem documented in `deps.py`.

### D5: `VehicleAccess` value object
**Rationale:** Carrying both the vehicle and a role flag avoids re-querying the share table in every route that only needs to know if the caller is the owner.
```python
@dataclass(frozen=True)
class VehicleAccess:
    vehicle: Vehicle
    is_owner: bool
```

### D6: Config redaction via `RedactedConfig` wrapper
**Rationale:** Returning `config: null` would require the frontend to handle a new union member and could break existing rendering paths. A wrapper with a `redacted: true` flag keeps the response shape consistent while hiding credential values.
**Response shape for sharees:**
```json
{
  "config": { "redacted": true }
}
```
**Frontend:** `VehicleCard` checks `is_owner` and only renders the Toyota/Generic config sections when `is_owner` is true.

### D7: `ListUserVehicles` queries owned + shared vehicles
**Rationale:** The "My Vehicles" page is the natural place for sharees to discover shared vehicles.
**Approach:**
1. Fetch owned vehicles via `VehicleRepository.get_all_by_owner_id(user_id)`.
2. Fetch shared vehicle ids via `VehicleShareRepository.list_vehicle_ids_for_user(user_id)`.
3. Fetch each shared vehicle via `VehicleRepository.get_by_id`.
4. Enrich both sets with latest location and `has_ser_tickets`, tagging each with `is_owner`.
**Trade-off:** This performs one query for owned vehicles plus N lookups for shared vehicles. Personal vehicle counts are small, so the N+1 cost is acceptable and keeps the repository interface simple.

### D8: Notification fan-out to owner + sharees with independent preferences
**Rationale:** Each recipient has their own notification preferences; a sharee should not receive pings they have disabled.
**Approach:** Both `NotificationDispatchHandler` and `SerTicketNotificationTriggerHandler` resolve a recipient list of `[owner_id] + sharee_ids`, then loop with per-recipient preference checks. Each recipient's failure is isolated (the existing broad try/except now wraps the loop body).
**Trade-off:** More notification-preference lookups and send calls. Mitigated by the small expected number of sharees per vehicle.

### D9: Share by email is immediate and idempotent
**Rationale:** No invite/acceptance state machine keeps the implementation small.
**Rules:**
- Unknown email → 404 with a generic "Vehicle or user not found" message to avoid email enumeration.
- Owner's own email → 422 (validation error); no share row is created.
- Already shared email → 201 with the full current sharee list; no duplicate row is created.
- Successful response includes each sharee's `user_id`, `display_name`, `email`, and `created_at`.
- All share mutation/list endpoints are rate-limited to 60 requests per minute to mitigate abuse.

### D10: Revoke supports owner and self
**Rationale:** A sharee should be able to remove themselves; an owner should be able to remove any sharee.
**Endpoint:** `DELETE /vehicles/{id}/shares/{user_id}` accepts the call if `current_user.id == owner_id` or `current_user.id == user_id`.

### D11: Automatic SER ticket creation remains owner-scoped
**Rationale:** Provider credentials, payment method, and `auto_create_ticket` preference belong to the owner. The event-driven handler already uses `vehicle.user_id`; after the rename it naturally uses `vehicle.owner_id`.

### D12: Database indexes for sharing and email lookup
**Rationale:** Sharing adds lookups by `vehicle_shares.user_id` ("which vehicles are shared with me?") and by `users.email` ("resolve email to user"). Without indexes the former becomes a sequential scan as shared-vehicle lists grow, and the latter is relied on by a frequent share-endpoint lookup.
**Indexes added:**
- `idx_vehicle_shares_user_id` on `vehicle_shares(user_id)`.
- Unique functional index `unique_lower_email` on `lower(users.email)` to enforce case-insensitive uniqueness and speed up `find_by_email`.

### D13: Metrics collection through a domain port
**Rationale:** Recording OpenTelemetry counters and histograms from application event handlers avoids importing infrastructure observability libraries directly into application code, preserving Clean Architecture boundaries. A domain `MetricsCollector` port defines record methods; an `OpenTelemetryMetricsCollector` adapter in infrastructure wires them to the configured meter provider.
**Impact:** Application handlers depend only on the domain port; the adapter is injected at startup in `app.py`.

### D14: POST /vehicles/{id}/shares returns the full sharee list
**Rationale:** Returning the entire list on every share operation lets the frontend replace its local state in one update without issuing a second GET call. It also makes the idempotent re-share response identical to a newly-created share.
**Response shape:** HTTP 201 with `{ "sharees": [ { "user_id", "display_name", "email", "created_at" } ] }`.

## Risks / Trade-offs

- **[Risk] Wide refactor from `user_id` → `owner_id`**: many tests and use cases reference the old name. → Mitigation: make the rename mechanical and exhaustive; run the full test suite after the migration.
- **[Risk] Authorization leak on future endpoints**: every new vehicle endpoint must choose the correct primitive. → Mitigation: centralize the two helpers in `deps.py` and document the rule in code comments; add tests that verify sharees receive 403 on every write endpoint.
- **[Risk] Notification fan-out increases external API calls**: each sharee with a enabled preference triggers a channel send. → Mitigation: keep recipient loops bounded by the small sharee count; monitor via existing notification dispatch metrics.
- **[Risk] Frontend config redaction shape**: the `RedactedConfig` wrapper is a new API shape the frontend must handle. → Mitigation: update TypeScript types and conditionally render config only when `is_owner` is true.
- **[Risk] Sharee sees location but cannot act on it**: sharees can view history but cannot submit locations or create tickets, which is intentional but may surprise users. → Documented in UI by hiding owner-only actions.

## Migration Plan

1. Create Alembic migration:
   - Rename `vehicles.user_id` → `owner_id`.
   - Create `vehicle_shares` table with composite PK and `ON DELETE CASCADE` on both FKs.
2. Update domain entities, ports, and repository implementations.
3. Update use cases and event handlers.
4. Update presentation layer (routes, dependencies, schemas).
5. Update frontend types and components.
6. Run `make test` and `make coverage`.
7. Deploy with migration first; rollback is the reverse migration.

## Open Questions

None at this time; all material scope decisions were resolved during exploration.
