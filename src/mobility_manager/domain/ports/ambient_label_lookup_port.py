"""
Port (interface): AmbientLabelLookupPort.

Abstract contract for resolving a license plate's DGT ambient label. Pure
plate-in, result-out — no vehicle_id, no persistence side effects.
Implementations (e.g. DgtAmbientLabelProvider) may raise on network/parse
failure; callers are responsible for catching it and mapping it to
`status=error` (see design.md decision 4).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)


@dataclass
class VehicleAmbientLabelResult:
    """Outcome of a single ambient label lookup for one plate."""

    status: AmbientLabelStatus
    label: AmbientLabel | None
    # Relative URL of the DGT sticker image, only set for found B/C/ECO/0
    # results — label A's confirmed-no-label response has no image.
    icon_relative_url: str | None = None


class AmbientLabelLookupPort(ABC):
    """Abstract port for looking up a plate's DGT ambient label."""

    @abstractmethod
    def lookup(self, license_plate: str) -> VehicleAmbientLabelResult:
        """
        Resolve the ambient label for the given plate.

        Raises on HTTP/parse failure — callers must catch and treat as a
        transient `error` status (see design.md decision 4).
        """
        ...

    @abstractmethod
    def download_icon(self, icon_relative_url: str) -> tuple[bytes, str]:
        """
        Download the sticker icon bytes referenced by a `lookup()` result's
        `icon_relative_url`.

        Returns a (image_bytes, content_type) tuple. Raises on HTTP failure
        — callers (LookupVehicleAmbientLabel) must catch it; a failed icon
        download never affects the already-resolved label.
        """
        ...
