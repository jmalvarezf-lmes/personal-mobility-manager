"""
Use case: FindNearestSerZone.

Finds the nearest SER parking zone for a given geographic location.
"""
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation


class FindNearestSerZone:
    """Use case that finds the nearest SER zone for a given location."""

    def __init__(self, repo: SerZoneRepository) -> None:
        self._repo = repo

    def execute(self, location: GeoLocation) -> SerZone:
        """
        Find the nearest SER zone.

        Raises SerZoneNotFoundError if no zone is found.
        """
        zone = self._repo.find_nearest(location)
        if zone is None:
            raise SerZoneNotFoundError(
                f"No SER zone found near ({location.lat}, {location.lng})"
            )
        return zone
