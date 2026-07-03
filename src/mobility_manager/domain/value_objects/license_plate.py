"""
Value object: LicensePlate.

Immutable, validated representation of a vehicle license plate.
"""

from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class LicensePlate:
    """Immutable license plate value object."""

    MAX_LENGTH: ClassVar[int] = 20

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > self.MAX_LENGTH:
            raise ValueError(f"License plate '{self.value}' exceeds maximum length of {self.MAX_LENGTH} characters.")
