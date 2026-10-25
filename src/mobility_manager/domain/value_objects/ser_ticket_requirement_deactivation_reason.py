"""
Domain value object: SerTicketRequirementDeactivationReason.

Closed enumeration of reasons why a SER ticket requirement deactivated.
This is the single source of truth for deactivation reasons.
"""

from enum import Enum, auto


class SerTicketRequirementDeactivationReason(Enum):
    """Reasons why a SER ticket requirement transitioned from active to inactive."""

    LEFT_ZONE = auto()
    ENFORCEMENT_INACTIVE = auto()
    TICKET_ACTIVE = auto()
    EXEMPT = auto()
