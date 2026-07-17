"""
Domain value object: AmbientLabel.

Closed enum of Spain's DGT "distintivo ambiental" environmental labels.
Serialized as DGT's own string values — note ZERO serializes as "0", not
"ZERO", so it round-trips directly against the DGT response and the
persisted `label` column.
"""

from enum import StrEnum


class AmbientLabel(StrEnum):
    """DGT environmental label values. No other value SHALL be persisted."""

    A = "A"
    B = "B"
    C = "C"
    ECO = "ECO"
    ZERO = "0"
