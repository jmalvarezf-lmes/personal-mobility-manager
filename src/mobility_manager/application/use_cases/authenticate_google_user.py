"""
Application use case: AuthenticateGoogleUser.

Provisions or retrieves a user from their Google identity claims, and ensures
a default user_preferences row exists for them.
"""

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.ports.user_repository import UserRepository


class AuthenticateGoogleUser:
    """
    Upsert a user from Google OAuth2 identity claims.

    Accepts the stable google_sub identifier alongside email and display_name.
    Delegates persistence to the UserRepository port (INSERT ON CONFLICT UPDATE),
    then ensures a default UserPreferences row exists for the upserted user via
    the UserPreferencesRepository port (INSERT ON CONFLICT DO NOTHING), so every
    user — new or existing — has a preferences row without a separate backfill
    migration.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        user_preferences_repo: UserPreferencesRepository,
    ) -> None:
        self._user_repo = user_repo
        self._user_preferences_repo = user_preferences_repo

    def execute(self, google_sub: str, email: str, display_name: str) -> User:
        """
        Provision or update a user, then provision default preferences for them.

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
        return user
