## MODIFIED Requirements

### Requirement: UserRepository upserts by google_sub
The system SHALL define a `UserRepository` port with:
- `upsert(google_sub: str, email: str, display_name: str) -> User` — inserts or updates the user record matching `google_sub`; always returns the persisted `User`
- `find_by_id(user_id: UUID) -> User | None` — returns the user for the given primary key, or `None`

The upsert SHALL update `email` and `display_name` if they differ from stored values (Google may change the display name or email).

The Google login flow SHALL also ensure a default `user_preferences` row exists for the upserted user (see `user-preferences` capability's "Login provisions default preferences for the user" requirement), immediately after the `users` upsert. This does not require a shared database transaction — see that requirement for why the two independently-atomic, idempotent writes are an accepted design choice.

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

#### Scenario: Login provisions preferences alongside the user upsert
- **WHEN** the Google login flow completes a `users` upsert for a user
- **THEN** a `user_preferences` row exists for that user's `id`, created with default values if it did not already exist
- **THEN** the `users` upsert and the preferences provisioning are each individually atomic; they are not required to share a single transaction
