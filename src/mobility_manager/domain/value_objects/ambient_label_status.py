"""
Domain value object: AmbientLabelStatus.

Three-way status for a vehicle's ambient label lookup attempt (see
add-ambient-label-lookup design.md decision 2). `FOUND` is terminal — the
scheduler's backlog query permanently excludes it. `NOT_FOUND` and `ERROR`
both represent "no confident answer" and are retried after a cooldown; they
are kept as separate values purely for observability (distinguishing "DGT
says no record" from "our request/parse failed"), not because retry
behavior differs between them.
"""

from enum import StrEnum


class AmbientLabelStatus(StrEnum):
    """Outcome of an ambient label lookup attempt."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    ERROR = "error"
