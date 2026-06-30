"""
Application use case: AuthenticateGoogleUser.

Provisions or retrieves a user from their Google identity claims.
"""

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.ports.user_repository import UserRepository


class AuthenticateGoogleUser:
    """
    Upsert a user from Google OAuth2 identity claims.

    Accepts the stable google_sub identifier alongside email and display_name.
    Delegates persistence to the UserRepository port (INSERT ON CONFLICT UPDATE).
    """

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def execute(self, google_sub: str, email: str, display_name: str) -> User:
        """
        Provision or update a user.

        Args:
            google_sub: Stable Google account identifier (the 'sub' claim).
            email: User's email address from Google.
            display_name: User's display name from Google.

        Returns:
            The persisted User entity.
        """
        return self._user_repo.upsert(
            google_sub=google_sub,
            email=email,
            display_name=display_name,
        )
