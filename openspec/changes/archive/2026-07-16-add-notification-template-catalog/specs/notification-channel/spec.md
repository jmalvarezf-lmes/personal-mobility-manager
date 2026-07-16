## REMOVED Requirements

### Requirement: Notification templates render localized text for a small, closed set of message kinds
**Reason**: The template-rendering mechanism has grown into its own concern — a filesystem-based, per-notification-type Jinja2 template catalog aligned with the `notification_types` preferences catalog — and now lives in the new `notification-templates` capability instead of alongside channel-transport concerns.

**Migration**: See the `notification-templates` capability's "render() renders localized notification text for a known type and language" requirement, which covers the same behavior (plus the new type-key alignment and fail-fast language-coverage validation). No caller-visible behavior changes: `render(type_key, language, **kwargs)` keeps the same signature and fallback semantics; only the message kind identifiers change (`vehicle_moved` → `location_moved`, `ser_ticket_required` → `ser_zone_ticket_required`), which is an internal rename with no effect on rendered text.
