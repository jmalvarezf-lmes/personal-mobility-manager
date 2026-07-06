## Context

`add-telegram-notification-channel` shipped the backend end-to-end (link-code, webhook linking, list/delete configured channels) but explicitly deferred two things: any frontend UI, and channel *preference* ("with only one possible channel, there's nothing to prefer between yet"). `SendNotification` currently fans out to every configured channel and nothing calls it in production — `NotificationDispatchHandler` is still a no-op subscriber to `VehicleLocationUpdated`. This change makes connecting/disconnecting channels usable from the UI and introduces the preferred-channel preference now that a second channel type is a real possibility, without deciding when a real notification actually fires (that stays deferred, same as before).

The closest existing UI precedent is `SerProvidersPage`, which hardcodes `KNOWN_PROVIDERS = ["elparking"]` client-side — an explicit, documented convention for "small, slow-changing enumerations." This change deliberately departs from that convention for notification channels: channel *connect flows* differ enough in shape (Telegram's async deep-link-then-webhook vs. a plausible future channel's synchronous form) that a real catalog endpoint is a better fit than a hardcoded array, and it means enabling/disabling a channel server-side (env-gating, same shape as `ENABLED_SER_PROVIDERS`) doesn't require a frontend deploy to match.

## Goals / Non-Goals

**Goals:**
- Users can connect and disconnect notification channels entirely from the UI (Telegram first, extensible to future channels without hardcoding which ones exist).
- The set of channels the system supports is discoverable via an API, not a hardcoded frontend list.
- Users can pick one preferred channel among their connected channels; `SendNotification` respects it.
- Preference state stays internally consistent: auto-selected on first connect, cleared on disconnect of the preferred channel, fails closed (no send) if ever inconsistent.

**Non-Goals:**
- Deciding *when* a real notification should fire (`NotificationDispatchHandler` stays a no-op; that's a subsequent change).
- Any channel beyond Telegram — the catalog and registry are built to accept more, but no second channel implementation is added here.
- Push/real-time delivery of link-confirmation to the browser — confirmation is via bounded polling, not WebSocket/SSE.
- Rich catalog metadata (e.g. a `connect_flow` discriminator) — the catalog returns bare channel ids; the frontend's id→component registry is the only place that knows how each channel's connect flow works.

## Decisions

### 1. Catalog endpoint: `GET /notifications/available-channels`, bare ids, authenticated
Returns `{"channels": ["telegram"]}`, sourced directly from `app.state.notification_channels.keys()` — the same dict already built in `app.py`'s lifespan setup, so there's exactly one place a new channel gets registered (no separate list to keep in sync). Kept authenticated for consistency with every other endpoint on this router, even though the payload isn't sensitive. Bare ids only, not richer per-channel metadata: display name/icon resolve client-side via i18n keys (matching `SerProvidersPage`'s `page.serProviders.providers.<id>` pattern), and the frontend's channel-id → connect-flow-component registry is unavoidably channel-specific code regardless of what the catalog returns, so a `connect_flow` discriminator wouldn't remove that registry — it would just add backend surface without eliminating the frontend mapping.

**Alternative considered**: env-gating this dict the way `ENABLED_SER_PROVIDERS` gates SER providers. Not done here — there's currently exactly one channel and no evidence yet that operators need to disable Telegram independently of code deploys; can be added later without changing the endpoint's shape.

### 2. `preferred_notification_channel` as a new nullable column on `user_preferences`
Mirrors the existing flat-schema convention (`default_ticket_duration_minutes`, `auto_create_ticket` — each its own column, not a JSON blob). `preferred_notification_channel TEXT NULL, REFERENCES nothing` (channels aren't a foreign-keyed table, they're names known only by the `notification_channels` dict at runtime — same treatment as `channel` in `user_notification_channel_configs`, which is also a bare `TEXT`). No default value: unset until a channel is connected (auto-select) or the user explicitly picks one in Preferences.

### 3. `SendNotification` becomes preferred-channel-only, fail-closed
Old behavior (fan out to every configured channel) is replaced: look up `preferred_notification_channel` from `UserPreferencesRepository`; if it's set and `UserNotificationChannelConfigRepository.find(user_id, preferred_channel)` returns a recipient, send only there; otherwise return `False` without sending anywhere — no fallback to "any connected channel." This is safe to change now because nothing in production calls `SendNotification` yet (`NotificationDispatchHandler` is a no-op), so there's no live fan-out behavior actually being relied upon.

**Alternative considered**: fall back to "any connected channel" if the preferred one is stale. Rejected — reintroduces the same "which one, and why" ambiguity the preference exists to remove, and silently sending through an un-chosen channel is a worse surprise than silently not sending until the user revisits Preferences.

### 4. Auto-select on first connect; clear on disconnect of the preferred channel
Both are small side effects layered onto existing use cases rather than new use cases:
- The Telegram webhook's linking success path (`config_repo.save(user_id, "telegram", ...)`) additionally checks `UserPreferencesRepository.find_by_user_id(user_id).preferred_notification_channel`; if `None`, it updates it to `"telegram"`.
- `RemoveNotificationChannel.execute` additionally checks whether the channel being removed equals the user's current `preferred_notification_channel`; if so, it clears the preference to `None` in the same operation.

Both sites currently number exactly one (there's one channel, one connect path, one remove use case), so this stays simple; a future second channel's connect path would need the same "auto-select if unset" check, same as Telegram's.

**Alternative considered**: a shared `ConnectNotificationChannel` use case that all channels funnel through, doing the auto-select centrally. Deferred — with only one real connect flow (Telegram's webhook-driven one) existing today, adding an abstraction for a currently-single caller mirrors the codebase's stated "widen little by little" discipline (same reasoning `NotificationChannelPort` itself used for not generalizing linking).

### 5. Link confirmation: bounded polling while the connect UI is open
`TelegramConnectFlow` component calls `GET /notifications/channels` on an interval (e.g. every 2–3s) after displaying the deep link, closing/resolving itself once `"telegram"` appears in the response, with a timeout (e.g. ~2 minutes) after which it stops polling and shows a "still waiting — you can close this and check back" state rather than polling forever. This is a new pattern for this frontend (no polling exists elsewhere today) but avoids new backend infrastructure (SSE/WebSocket) for a single channel's async edge case.

### 6. Frontend: catalog-driven list, registry-driven connect UI
`NotificationChannelsPage` fetches both `GET /notifications/available-channels` (catalog) and `GET /notifications/channels` (configured), and renders one row per catalog entry showing connected/not-connected state — same list/connect-modal/disconnect shape as `SerProvidersPage`, but the *set of rows* comes from the API instead of a hardcoded array. A local `Record<string, ComponentType<ConnectFlowProps>>` registry maps channel id → its connect-flow component (only `"telegram": TelegramConnectFlow` for now); an unrecognized id from the catalog with no registered component renders a disabled/"not yet supported" row rather than crashing, so a future channel appearing in the catalog before its frontend component ships degrades gracefully.

## Risks / Trade-offs

- **[Risk] Changing `SendNotification` from fan-out to single-preferred-channel is a behavior change.** → Mitigated: no production caller exists yet (`NotificationDispatchHandler` is still a no-op), so there's no live behavior being altered from a user's perspective.
- **[Risk] Polling is a new frontend pattern with no precedent in this codebase; a naive implementation could poll forever or leak intervals on unmount.** → Mitigate with an explicit bounded attempt count/timeout and cleanup on component unmount.
- **[Trade-off] Catalog endpoint returns bare ids, meaning the frontend needs its own id→component registry regardless.** → Accepted: richer catalog metadata wouldn't remove the need for channel-specific connect-flow code, so it would add backend complexity without removing frontend complexity.
- **[Risk] Auto-select and clear-on-disconnect logic lives inline in two separate call sites (webhook handler, remove use case) rather than a shared abstraction.** → Accepted for now per "widen little by little"; revisit if/when a second channel's connect flow needs the same check, at which point a shared helper becomes justified by two real call sites instead of one.

## Migration Plan

1. Add Alembic migration adding `preferred_notification_channel TEXT NULL` to `user_preferences`.
2. Deploy backend: new catalog endpoint, updated `SendNotification`, `RemoveNotificationChannel`, and Telegram webhook auto-select logic, updated `GET`/`PUT /preferences` schemas.
3. Deploy frontend: Notification Channels page, Telegram connect-flow component, Preferences page's new selector.
4. Rollback: revert code; drop the added column (no data loss beyond the new preference itself, which has no prior production users since it doesn't exist yet).

## Open Questions

None outstanding — resolved during exploration (see prior `/opsx:explore` session): preferred-channel semantics, fail-closed stale-preference behavior, auto-select-on-first-connect, clear-on-disconnect, polling-based link confirmation, and bare-id catalog shape were all decided there.
