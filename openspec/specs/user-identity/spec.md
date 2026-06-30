## ADDED Requirements

### Requirement: User entity represents an authenticated person
The system SHALL define a `User` domain entity with fields: `id` (UUID), `google_sub` (str), `email` (str), `display_name` (str), `created_at` (datetime). `google_sub` is Google's stable, unique identifier for the user (`sub` claim in the ID token) and SHALL be used as the lookup key on login.

#### Scenario: User entity is immutable value object
- **WHEN** a `User` is constructed from database fields
- **THEN** it is a frozen dataclass (or equivalent) with all five fields populated
- **THEN** `google_sub` uniquely identifies the user across sessions

---

### Requirement: users table persists user records
The system SHALL create a `users` table with columns: `id UUID PRIMARY KEY`, `google_sub TEXT NOT NULL UNIQUE`, `email TEXT NOT NULL`, `display_name TEXT NOT NULL`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`. The `google_sub` column SHALL have a unique index to enable O(1) upsert-by-sub lookups.

#### Scenario: users table schema
- **WHEN** the migration is applied
- **THEN** the `users` table exists with all five columns and a unique constraint on `google_sub`

---

### Requirement: UserRepository upserts by google_sub
The system SHALL define a `UserRepository` port with:
- `upsert(google_sub: str, email: str, display_name: str) -> User` — inserts or updates the user record matching `google_sub`; always returns the persisted `User`
- `find_by_id(user_id: UUID) -> User | None` — returns the user for the given primary key, or `None`

The upsert SHALL update `email` and `display_name` if they differ from stored values (Google may change the display name or email).

#### Scenario: First login inserts a new user
- **WHEN** `upsert` is called with a `google_sub` not yet in the database
- **THEN** a new row is inserted and the returned `User` has a freshly generated `id` and `created_at`

#### Scenario: Subsequent login updates mutable fields
- **WHEN** `upsert` is called with a `google_sub` already in the database and a different `email`
- **THEN** no new row is inserted
- **THEN** the existing row's `email` is updated
- **THEN** the returned `User` has the same `id` as the existing row

#### Scenario: find_by_id returns None for unknown id
- **WHEN** `find_by_id` is called with a UUID that does not exist in `users`
- **THEN** the method returns `None` without raising
