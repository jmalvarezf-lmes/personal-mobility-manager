"""
Port (interface): SerEnforcementSchedule.

Abstract contract for evaluating whether SER enforcement is currently in
effect for a given city, per its weekday hours, calendar exceptions
(August, Dec 24/31), and public holidays — see add-ser-enforcement-calendar
design.md D4.
"""

from abc import ABC, abstractmethod


class SerEnforcementSchedule(ABC):
    """Abstract port for evaluating per-city SER enforcement status."""

    @abstractmethod
    def is_active_now(self, city_code: str) -> bool:
        """
        Return whether SER enforcement is currently active for `city_code`.

        Evaluated against "now" in a hardcoded timezone (see
        PostgresSerEnforcementSchedule.ENFORCEMENT_TIMEZONE — design.md D9;
        not stored in the `cities` table and not exposed as a setting in
        this change, a placeholder for a future per-user/per-city
        preference), in precedence order: Sunday (absolute) -> holiday
        (absolute) -> fixed_date exception -> month exception -> weekday
        hours. See design.md D4 for the full precedence rules.
        """
        ...
