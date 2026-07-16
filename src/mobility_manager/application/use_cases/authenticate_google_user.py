"""
Application use case: AuthenticateGoogleUser.

Provisions or retrieves a user from their Google identity claims, and
ensures a default user_preferences row and a full set of (disabled)
notification preference rows exist for them.
"""

import logging

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.ports.notification_preferences_repository import (
    NotificationPreferencesRepository,
)
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.ports.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AuthenticateGoogleUser:
    """
    Upsert a user from Google OAuth2 identity claims.

    Accepts the stable google_sub identifier alongside email and display_name.
    Delegates persistence to the UserRepository port (INSERT ON CONFLICT UPDATE),
    then ensures a default UserPreferences row exists for the upserted user via
    the UserPreferencesRepository port (INSERT ON CONFLICT DO NOTHING), so every
    user — new or existing — has a preferences row without a separate backfill
    migration. Alongside that, ensures a disabled (enabled=false, config={})
    notification preference row exists for every notification_types catalog
    entry via NotificationPreferencesRepository.ensure_defaults — a user is
    never automatically opted into a notification type, including on their
    very first login.

    The notification_preferences_repo.ensure_defaults call is guarded by its
    own try/except: it's a self-healing provisioning step (same pattern as
    UserPreferencesRepository.ensure_default — see
    openspec/specs/user-preferences/spec.md's "Login provisions default
    preferences" requirement), so a transient failure there (e.g. a DB
    error) is logged and swallowed rather than failing the whole login —
    the user record has already been upserted successfully by that point,
    and any missing notification preference rows self-heal on the user's
    next login attempt instead.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        user_preferences_repo: UserPreferencesRepository,
        notification_preferences_repo: NotificationPreferencesRepository,
    ) -> None:
        self._user_repo = user_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo

    def execute(self, google_sub: str, email: str, display_name: str) -> User:
        """
        Provision or update a user, then provision default preferences
        (both user preferences and per-type notification preferences) for
        them.

        Args:
            google_sub: Stable Google account identifier (the 'sub' claim).
            email: User's email address from Google.
            display_name: User's display name from Google.

        Returns:
            The persisted User entity.
        """
        user = self._user_repo.upsert(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
        )
        self._user_preferences_repo.ensure_default(user.id)
        try:
            self._notification_preferences_repo.ensure_defaults(user.id)
        except Exception:
            logger.exception(
                "Failed to provision default notification preferences for user %s; "
                "will self-heal on next login",
                user.id,
            )
        return user
