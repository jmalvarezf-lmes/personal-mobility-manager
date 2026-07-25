"""
Presentation: FastAPI dependencies for authenticated user resolution and
per-vehicle ownership enforcement.

get_current_user reads the session JWT cookie, validates it with PyJWT,
extracts the `sid` claim, and calls ValidateSession to confirm the
server-side session referenced by `sid` still exists, isn't revoked, isn't
expired, and belongs to the JWT's `sub` — this is the security-critical
server-side revocation check (see add-session-revocation design.md); a
cryptographically valid but revoked/expired/mismatched session is rejected
even though the JWT signature itself still verifies. Only then does it fetch
and return the User entity. Raises HTTP 401 on any failure — missing
cookie, invalid token, failed session validation, or unknown user.

Ownership enforcement has two entry points sharing one private helper
(_fetch_owned_vehicle), rather than a single `Depends()` used everywhere.
FastAPI resolves all `Depends(...)` parameters — including sub-dependencies —
before it parses or validates the request body, so a route that both takes a
body and depends on an ownership check would let the 404/403 short-circuit
*before* the body is ever validated, reordering behavior relative to an
inline check (which historically ran after the body had already been bound).
That lets a non-owner learn "this vehicle exists and isn't yours" with an
empty or malformed body, instead of requiring a crafted valid payload first.
See design.md decision 5 (amended after the post-implementation 4R review)
for the full rationale.

- `require_owned_vehicle` — a `Depends()` target — is used on the four
  routes with no request body, where dependency-vs-body ordering is moot.
- `get_owned_vehicle_or_raise` — a plain function, not a `Depends()` target —
  is called manually as the first line inside the two route handlers that do
  take a body, *after* the body parameter has already resolved, restoring
  the original body-then-ownership order exactly.
"""

from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request

from mobility_manager.config import get_jwt_secret
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository

_JWT_ALGORITHM = "HS256"


def decode_session_jwt(token: str) -> dict[str, Any]:
    """
    Decode and verify the session JWT (HS256, signed with JWT_SECRET).

    Raises jwt.PyJWTError (or a subclass) on any failure — expired,
    malformed, or tampered token. Callers decide how to handle it. Shared by
    get_current_user and auth.py's logout, which both need to decode the
    same cookie the same way.
    """
    return jwt.decode(token, get_jwt_secret(), algorithms=[_JWT_ALGORITHM])


async def get_current_user(request: Request) -> User:
    """
    FastAPI dependency that resolves the authenticated User from the session cookie.

    Reads the 'session' cookie, decodes the HS256 JWT, validates the
    server-side session referenced by the JWT's `sid` claim via
    ValidateSession (not revoked, not expired, owned by the JWT's `sub`),
    and fetches the user from the repository stored in app.state. Raises
    HTTP 401 on any failure — missing cookie, invalid token, invalid
    session, or unknown user.
    """
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_session_jwt(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from None

    sid_str: str | None = payload.get("sid")
    if not sid_str:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID in session") from None

    try:
        session_id = UUID(sid_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session ID in session") from None

    validate_session_uc = request.app.state.validate_session
    if not validate_session_uc.execute(session_id=session_id, user_id=user_id):
        raise HTTPException(status_code=401, detail="Session is no longer valid")

    user_repo = request.app.state.user_repo
    user: User | None = user_repo.find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def _fetch_owned_vehicle(vehicle_repo: VehicleRepository, vehicle_id: UUID, current_user: User) -> Vehicle:
    """
    Fetch `vehicle_id` from `vehicle_repo` and enforce ownership.

    Raises HTTP 404 if the vehicle doesn't exist, HTTP 403 if it exists but
    isn't owned by the authenticated user. Returns the Vehicle entity
    otherwise. Shared by both `require_owned_vehicle` and
    `get_owned_vehicle_or_raise` — see module docstring for why there are two
    entry points.
    """
    vehicle: Vehicle | None = vehicle_repo.get_by_id(vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    if vehicle.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this vehicle")

    return vehicle


async def require_owned_vehicle(
    vehicle_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Vehicle:
    """
    FastAPI dependency that fetches `vehicle_id` and enforces ownership.

    Use this on routes with no request body. Do NOT use it on routes that
    also take a body — see module docstring.
    """
    return _fetch_owned_vehicle(request.app.state.vehicle_repo, vehicle_id, current_user)


def get_owned_vehicle_or_raise(request: Request, vehicle_id: UUID, current_user: User) -> Vehicle:
    """
    Plain function (NOT a `Depends()` target) that fetches `vehicle_id` and
    enforces ownership.

    Call this manually as the first line of a route handler's body, after
    its `body: ...Request` parameter has already resolved, so body
    validation still runs before the ownership check — see module docstring.
    """
    return _fetch_owned_vehicle(request.app.state.vehicle_repo, vehicle_id, current_user)
