"""
Presentation: FastAPI dependency for authenticated user resolution.

Reads the session JWT cookie, validates it with PyJWT, and returns the User entity.
Raises HTTP 401 on any auth failure — missing cookie, invalid token, or unknown user.
"""

from uuid import UUID

import jwt
from fastapi import HTTPException, Request

from mobility_manager.config import get_jwt_secret
from mobility_manager.domain.entities.user import User


async def get_current_user(request: Request) -> User:
    """
    FastAPI dependency that resolves the authenticated User from the session cookie.

    Reads the 'session' cookie, decodes the HS256 JWT, and fetches the user
    from the repository stored in app.state. Raises HTTP 401 on any failure.
    """
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in session") from None

    user_repo = request.app.state.user_repo
    user: User | None = user_repo.find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user
