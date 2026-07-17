"""
Application use case: LookupVehicleAmbientLabel.

Given a vehicle_id + license_plate, resolves and persists the vehicle's DGT
ambient label, and — on a B/C/ECO/0 result — caches the label's sticker icon
on a cache miss (see design.md decisions 1, 2, and 8).

Never raises: this use case is called both synchronously from
RegisterVehicle.execute() (which must never fail because of it — design.md
decision 4) and from AmbientLabelScheduler (which must keep going after one
vehicle's failure — design.md decision 5). Every failure from the lookup
port or icon download is caught, logged, and persisted as `status=error`
(the lookup failure) without re-raising; an icon-download failure never
un-resolves an already-found label.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from mobility_manager.domain.ports.ambient_label_icon_repository import (
    AmbientLabelIconRepository,
)
from mobility_manager.domain.ports.ambient_label_lookup_port import (
    AmbientLabelLookupPort,
)
from mobility_manager.domain.ports.vehicle_ambient_label_repository import (
    VehicleAmbientLabelRepository,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)
from mobility_manager.infrastructure.observability.metrics import (
    record_ambient_label_lookup,
)

logger = logging.getLogger(__name__)

# Only these four labels have a physical DGT sticker to cache and serve —
# category A's alert-warning response contains no image (design.md decision 8).
_ICON_ELIGIBLE_LABELS = frozenset({AmbientLabel.B, AmbientLabel.C, AmbientLabel.ECO, AmbientLabel.ZERO})


class LookupVehicleAmbientLabel:
    """Resolve and persist a vehicle's DGT ambient label; never raises."""

    def __init__(
        self,
        lookup_port: AmbientLabelLookupPort,
        label_repo: VehicleAmbientLabelRepository,
        icon_repo: AmbientLabelIconRepository,
    ) -> None:
        self._lookup_port = lookup_port
        self._label_repo = label_repo
        self._icon_repo = icon_repo

    def execute(self, vehicle_id: UUID, license_plate: str) -> None:
        """
        Look up `license_plate`'s ambient label and persist the result for
        `vehicle_id`. Swallows and logs any exception from the lookup port
        or the icon cache/download path — never propagates.
        """
        now = datetime.now(UTC)

        try:
            result = self._lookup_port.lookup(license_plate)
        except Exception:
            logger.exception("Ambient label lookup failed for vehicle %s", vehicle_id)
            record_ambient_label_lookup(status=AmbientLabelStatus.ERROR.value)
            self._label_repo.upsert(vehicle_id, None, AmbientLabelStatus.ERROR, now)
            return

        record_ambient_label_lookup(status=result.status.value)
        self._label_repo.upsert(vehicle_id, result.label, result.status, now)

        if result.status == AmbientLabelStatus.FOUND and result.label in _ICON_ELIGIBLE_LABELS:
            self._ensure_icon_cached(result.label, result.icon_relative_url)

    def _ensure_icon_cached(self, label: AmbientLabel, icon_relative_url: str | None) -> None:
        """Download and cache `label`'s icon only on a cache miss (design.md decision 8)."""
        if self._icon_repo.get_by_label(label) is not None:
            return  # already cached — never re-downloaded

        if icon_relative_url is None:
            logger.warning("Resolved label %s with no icon URL to cache", label.value)
            return

        try:
            image_bytes, content_type = self._lookup_port.download_icon(icon_relative_url)
        except Exception:
            logger.exception("Ambient label icon download failed for label %s", label.value)
            return

        self._icon_repo.save(label, image_bytes, content_type)
