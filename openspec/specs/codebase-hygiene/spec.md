### Requirement: `.env.example` only lists variables the application reads
`.env.example` SHALL only declare environment variables that are read by at least one module under `src/mobility_manager/` (directly via `os.environ`/`os.getenv`, or indirectly through a documented renamed/legacy variable name).

#### Scenario: Unused variable is found
- **WHEN** a variable declared in `.env.example` has zero `os.environ`/`os.getenv` reads anywhere in `src/`
- **THEN** it MUST be removed from `.env.example` and from `README.md`'s environment variable table, rather than left in place as a reserved/dead entry

### Requirement: Domain ports, use cases, and adapters are only kept while consumed
The system SHALL NOT retain a domain port, application use case, or infrastructure adapter that has no consumer (no router, scheduler, CLI entry point, registry lookup, or other application/presentation-layer caller) anywhere in the codebase.

#### Scenario: A port/use-case/adapter chain becomes fully unreferenced
- **WHEN** a domain port's only implementation and the only use case depending on it are never imported by any router, scheduler, CLI entry point, or registry outside their own definitions
- **THEN** the port, the use case, and the adapter MUST be deleted together rather than left in the tree as latent stubs

#### Scenario: A file is self-documented as a tombstone
- **WHEN** a file's own module docstring or comment states it is kept only as a placeholder/tombstone for a past rename or replacement
- **THEN** the file MUST be deleted once confirmed there is no other in-flight branch still referencing the old name
