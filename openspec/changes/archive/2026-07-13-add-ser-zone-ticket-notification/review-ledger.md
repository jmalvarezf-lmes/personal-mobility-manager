# Review Ledger — add-ser-zone-ticket-notification

4R pass (>400 changed lines triggered full fan-out): risk, resilience, readability, reliability.

| id | lens | location | severity | status | evidence |
|----|------|----------|----------|--------|----------|
| R4-001 | resilience | ser_ticket_trigger_handler.py (whole `handle`) + app.py:241,248 (subscription order) + in_memory_event_publisher.py:36-42 | BLOCKER | fixed | New handler subscribed ahead of `NotificationDispatchHandler` on an unguarded synchronous publish loop. Any exception in the new handler now prevents the pre-existing movement notification from firing for that event. |
| R4-002 | resilience | send_notification.py:63-79 called from ser_ticket_trigger_handler.py; propagates via record_vehicle_location.py:93-102 to vehicles.py push endpoint | BLOCKER | fixed | `SendNotification` deliberately lets `NotificationChannelApiError` propagate. Called synchronously in the new handler with no containment, so a Telegram failure now surfaces as an unhandled 500 on the push endpoint even though the location was already persisted. |
| R4-003 | resilience | whole handler/publisher chain | CRITICAL | wont-fix | No observability/alerting exists anywhere in this codebase (not Sentry, not metrics) — pre-existing systemic gap, not introduced by this diff, and out of scope for a notification-only change. Noted, not blocking. |
| R4-004 | resilience | ser_ticket_trigger_handler.py (zone lookup) | WARNING | fixed | Degraded zone-data dependency (DB error) not distinguished from "no zone found." Resolved by the same containment fix as R4-001/002. |
| R4-005 | resilience | ser_ticket_trigger_handler.py (repo calls) | WARNING | fixed | No guard around `get_previous`/vehicle lookup failures. Resolved by the same containment fix. |
| R2-001 | readability | ser_ticket_trigger_handler.py docstring/control-flow vs notification_dispatch_handler.py | WARNING | fixed | Docstring claims parity with the sibling handler's check, but vehicle-lookup ordering and first-location handling actually diverged. Fixed by reordering to match the sibling exactly (vehicle lookup first) and calling out the remaining intentional divergence (first-ever location still proceeds to zone check) explicitly in a comment. |
| R2-002 | readability | ser_ticket_trigger_handler.py (assert on zone) | SUGGESTION | fixed | `assert zone is not None` is a strippable invariant coupling handler logic to `DetermineSerTicketRequirement`'s internals. Replaced with an explicit `if zone is None: return` guard. Same issue as R3-001. |
| R2-003 | readability | test_ser_ticket_trigger_handler.py (fixture duplication) | SUGGESTION | wont-fix | Matches existing test-style conventions elsewhere in the repo; not a regression introduced by this diff. |
| R3-001 | reliability | ser_ticket_trigger_handler.py:99 | WARNING | fixed | Same as R2-002 — assert replaced with explicit guard. |
| R3-002 | reliability | ser_ticket_trigger_handler.py call order untested | WARNING | fixed | Resolved by reordering handler to check vehicle existence before zone/requirement checks (matches sibling, avoids wasted geo lookups for phantom vehicle_ids). |
| R3-003 | reliability | test_ser_ticket_trigger_handler.py:369-392 | WARNING | fixed | `test_missing_vehicle_is_skipped_without_error` updated to assert `find_containing.calls == []` and `determine_requirement.calls == []` (never called), now that vehicle lookup short-circuits first. Verified: all 10 handler tests pass. |
| R3-004 | reliability | test_ser_ticket_trigger_handler.py:414-425 (provider-absence test) | SUGGESTION | wont-fix | Implementation-centric signature check; low value to strengthen given mypy already guards constructor shape. Accepted as-is. |
| R3-005 | reliability | test_ser_ticket_trigger_handler.py boundary coverage | SUGGESTION | fixed | Added an exact-threshold boundary test case. |

**Risk lens (R1): no findings.**
