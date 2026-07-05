## Context

SER ticket creation (a future change) needs a provider abstraction, since different city/operator apps have different login and ticket-creation mechanics. Only one concrete provider is planned, but the interface must not assume its specifics. This is genuinely new territory: `ParkingServicePort`, `ParkingTicket`, and `GetParkingTicketUseCase` exist today only as empty stubs — there is no working analog to extend, only conventions to borrow from `vehicle_configs`/`BrandRegistry` (per-vehicle credential storage + brand-keyed provider registry).

A key departure from the vehicle-provider pattern: `VehiclePullLocationPort.fetch_location(vehicle_id, config)` has no explicit login step — Toyota's adapter constructs a fresh API client and authenticates inline on every call, because Toyota's auth is effectively free/stateless from this codebase's perspective. SER ticket providers are different: login is mandatory for every provider (not incidental like Toyota's), is user-scoped (not vehicle-scoped, since a parking-app account isn't tied to one vehicle), produces a token/session that must be persisted and reused across many ticket creations, and needs eventual renewal via provider-specific logic. This justifies a two-step port (`login` then `create_ticket`) rather than credentials-per-call.

Separately, ticket creation should eventually be triggered by vehicle location updates. Rather than a direct in-process Observer (GoF-style, tightly coupled to `RecordVehicleLocation` calling registered objects directly), the chosen shape is a lightweight event-publishing mechanism: `RecordVehicleLocation` publishes a `VehicleLocationUpdated` domain event through an `EventPublisher` port, and a separate handler subscribes to it. This is architecturally an Observer under the hood for the in-memory adapter, but the port boundary is drawn so a future real message broker (SQS, Kafka, etc.) can replace the adapter without touching `RecordVehicleLocation` or the handler.

## Goals / Non-Goals

**Goals:**
- Define `SerTicketProviderPort` (login + create_ticket) and a registry that can hold zero or more concrete providers, exactly mirroring `BrandRegistry`'s shape and "empty is valid" behavior.
- Provide per-user encrypted credential/session storage, keyed by `(user_id, provider)`, following the same encrypt-and-store convention as `vehicle_configs`.
- Flesh out `ParkingTicket` and persist it via a new repository, so `CreateSerTicket` produces something real and inspectable.
- Provide `ConnectSerTicketProvider` and `CreateSerTicket` use cases that are fully wired and unit-testable against a fake provider, even though nothing in production calls them yet.
- Introduce `EventPublisher` (port) + `InMemoryEventPublisher` (adapter) + `VehicleLocationUpdated` (event), wired into `RecordVehicleLocation`, with a registered-but-no-op `SerTicketTriggerHandler`.

**Non-Goals:**
- No concrete `SerTicketProviderPort` implementation (e.g. a specific city/operator adapter) — that is a later change.
- No "is this vehicle inside a SER zone" logic, no reading of `user_preferences.auto_create_ticket`/`default_ticket_duration_minutes`, no actual ticket-creation trigger decision — `SerTicketTriggerHandler` is a no-op body in this change. Behavior will be "widened little by little" in follow-up changes.
- No HTTP endpoints — `ConnectSerTicketProvider` and `CreateSerTicket` are exercised only by unit tests against a fake provider.
- No session renewal logic — each provider will handle its own renewal strategy when it's built; this change doesn't prescribe a `renew`/`refresh` port method.
- No real event bus / message broker — the in-memory adapter is synchronous and in-process only.

## Decisions

### 1. `SerTicketProviderPort` with `SerProviderCredentials`/`SerProviderSession` value objects
```python
@dataclass(frozen=True)
class SerProviderCredentials:
    data: dict[str, Any]

@dataclass(frozen=True)
class SerProviderSession:
    data: dict[str, Any]

class SerTicketProviderPort(ABC):
    def login(self, credentials: SerProviderCredentials) -> SerProviderSession: ...
    def create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket: ...
```
`SerProviderCredentials`/`SerProviderSession` are thin domain value objects, mirroring `ToyotaConfig`'s role: a named, typed thing crosses the port boundary rather than a bare dict, so the signature is self-documenting and consistent with the rest of this codebase's convention (every other provider-facing port — `VehiclePullLocationPort.fetch_location(vehicle_id, config: ToyotaConfig)` — takes a named value object, never a raw dict). The `data: dict[str, Any]` field inside each is still provider-defined and opaque to the port itself, since only one concrete provider is planned and its exact shape isn't known yet — so this is intentionally "just a wrapper" for now. The repository layer JSON-serializes and Fernet-encrypts `session.data`, exactly mirroring how `PostgresVehicleConfigRepository` treats Toyota's credential payload today.

Alternative considered: opaque `dict[str, Any]` directly at the port boundary, no wrapper type. Rejected on reflection — it breaks with this codebase's established convention of typed value objects crossing port boundaries (`ToyotaConfig`, `GenericConfig`), and the wrapper costs nothing extra now while keeping the interface's calling code readable and consistent, even though the wrapped payload remains generic until a concrete provider is built.

### 2. `SerTicketProviderRegistry` mirrors `BrandRegistry`
Same shape as `infrastructure/vehicle_providers/brand_registry.py`: a registry class returning the set of available providers (here, likely `dict[str, SerTicketProviderPort]` keyed by provider name, or an empty mapping — exact return type decided at implementation time to match `BrandRegistry`'s list-returning convention as closely as sensible). Registers zero providers today, since no concrete provider exists.

### 3. Per-user credential storage: `user_ser_provider_configs`
```
user_ser_provider_configs
  user_id UUID  ┐
  provider TEXT ├─ composite PK (mirrors vehicle_configs' (vehicle_id, brand) shape)
  encrypted_payload BYTEA NOT NULL   -- Fernet-encrypted JSON of whatever login() returned
  updated_at TIMESTAMPTZ NOT NULL
```
Scoped to `user_id` (not `vehicle_id`) because SER provider accounts are personal, not per-vehicle — a real departure from `vehicle_configs`, called out explicitly since it's easy to default to copying the wrong key.

### 4. `ParkingTicket` entity + `parking_ticket_repository`
```python
@dataclass(frozen=True)
class ParkingTicket:
    id: UUID
    vehicle_id: UUID
    user_id: UUID
    provider: str
    duration_minutes: int
    provider_reference: str | None   # opaque confirmation/ticket-id from the provider, if any
    created_at: datetime
```
`provider_reference` stays optional and opaque (a string, not structured) since we don't know what a concrete provider will hand back as a confirmation. `parking_tickets` table mirrors this shape directly.

### 5. `ConnectSerTicketProvider` and `CreateSerTicket` use cases, no HTTP surface
- `ConnectSerTicketProvider.execute(user_id, provider, credentials: SerProviderCredentials) -> None`: resolves the provider from the registry, calls `login(credentials)`, persists the resulting session via the config repository.
- `CreateSerTicket.execute(user_id, vehicle_id, provider, duration_minutes) -> ParkingTicket`: loads the vehicle (ownership check against `user_id`), loads the user's stored session for `(user_id, provider)`, resolves the provider instance from the registry, calls `create_ticket`, persists and returns the resulting `ParkingTicket`. `provider` is an explicit argument rather than inferred, since a user could in principle connect more than one provider even though only one concrete provider exists today — this matches the `(user_id, provider)` key the config storage already uses, so there's no separate "which provider" resolution logic to invent.

Both are unit-tested against a fake/test double implementing `SerTicketProviderPort`, proving the orchestration without any real provider or endpoint.

### 6. Event-driven trigger instead of direct Observer
```python
class EventPublisher(ABC):
    def publish(self, event: DomainEvent) -> None: ...

class InMemoryEventPublisher(EventPublisher):
    # dict[type[DomainEvent], list[Handler]], synchronous, in-process dispatch
    def subscribe(self, event_type, handler) -> None: ...
    def publish(self, event) -> None: ...
```
`RecordVehicleLocation.execute()` calls `self._event_publisher.publish(VehicleLocationUpdated(...))` immediately after `location_repo.save(location)`, for both pull and push sources. `SerTicketTriggerHandler` is subscribed to `VehicleLocationUpdated` at startup in `app.py`, with a no-op `handle()` body.

Chose a hand-rolled port + in-memory adapter over adopting the `eventsourcing` library: that library is designed around event sourcing as the persistence model for aggregates (state reconstructed from an event stream), which would require re-architecting `Vehicle`/`VehicleLocation` as event-sourced aggregates — a much bigger commitment than what's needed here (decoupled notification, in-memory now, swappable transport later). A one-method `EventPublisher` port achieves the "swap the adapter later" goal with zero new dependencies and zero conceptual mismatch with the rest of this Clean-Architecture codebase.

Dispatch is synchronous and in-process for this change (no threading/async), since the only registered handler is a no-op. The port signature doesn't promise sync-or-async, so a future real-broker adapter isn't boxed in by this choice.

## Risks / Trade-offs

- **[Risk] Nothing in this change is exercised in production (no HTTP surface, no-op handler).** → Mitigation: accepted trade-off per explicit scope decision; correctness is proven by unit tests against a fake provider, and the concrete-provider change will be the first real end-to-end proof.
- **[Risk] `SerProviderCredentials.data`/`SerProviderSession.data` are still opaque `dict[str, Any]` internally, so the wrapper doesn't give compile-time shape-checking on the payload itself.** → Mitigation: acceptable since only one provider is planned and its shape is unknown; each concrete provider can validate its own dict internally (e.g. with a Pydantic model at the infrastructure boundary) without the port needing to know about it. The wrapper still gives type identity at the port boundary (you can't pass a random dict where a session is expected), which was the main convention this decision was trying to match.
- **[Trade-off] In-memory `EventPublisher` means events are lost on process restart and don't survive across multiple app instances.** → Acceptable for a single-instance deployment today; the port boundary is exactly what makes swapping to a durable/distributed adapter later a contained change.

## Migration Plan

1. Add two Alembic migrations: `user_ser_provider_configs` and `parking_tickets`.
2. Deploy domain/application/infrastructure code — no behavior change since the event handler is a no-op and nothing has an HTTP surface.
3. Rollback: standard Alembic downgrades drop both tables; no data loss beyond structures that were never populated in production use.

## Open Questions

None outstanding — `CreateSerTicket`'s provider resolution (Decision 5) and all other design points are settled.
