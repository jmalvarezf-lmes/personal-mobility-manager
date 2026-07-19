## ADDED Requirements

### Requirement: GET /cities lists all registered cities
The system SHALL expose `GET /cities` returning a JSON array of all rows in the `cities` table, each with `code` and `name`. This endpoint requires no authentication and SHALL always reflect the live table contents.

#### Scenario: Successful query returns all cities
- **WHEN** a GET request is made to `/cities`
- **THEN** the response status is 200 with a JSON array where each element has `code` and `name`, matching every row currently in the `cities` table

#### Scenario: A newly seeded city appears without a code change
- **WHEN** a new row is added to the `cities` table
- **THEN** a subsequent `GET /cities` request includes it, with no application code change required
