"""
Port (interface): AmbientLabelIconRepository.

Abstract contract for the DGT sticker icon cache, keyed by label value
(B/C/ECO/0 only — label A never has an icon, see design.md decision 8).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mobility_manager.domain.value_objects.ambient_label import AmbientLabel


@dataclass
class AmbientLabelIcon:
    """Cached icon bytes plus the content type to serve them with."""

    image_bytes: bytes
    content_type: str


class AmbientLabelIconRepository(ABC):
    """Abstract repository for cached ambient label icon images."""

    @abstractmethod
    def get_by_label(self, label: AmbientLabel) -> AmbientLabelIcon | None:
        """Return the cached icon for the label, or None on a cache miss."""
        ...

    @abstractmethod
    def save(self, label: AmbientLabel, image_bytes: bytes, content_type: str) -> None:
        """Cache the icon bytes (and content type) for the given label."""
        ...
