"""
Use case: FindContainingSerZone.

Finds the SER zone that contains a given geographic location, if any.
Unlike FindNearestSerZone, "not inside any zone" is a valid, expected
outcome — not an error — so this use case returns None rather than raising.
"""

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation


class FindContainingSerZone:
    """Use case that finds the SER zone containing a given location, if any."""

    def __init__(self, repo: SerZoneRepository) -> None:
        self._repo = repo

    def execute(self, location: GeoLocation) -> SerZone | None:
        """Return the containing SerZone, or None if the location is inside no zone."""
        return self._repo.find_containing(location)
