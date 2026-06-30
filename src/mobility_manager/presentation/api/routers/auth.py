"""
Presentation: Auth API router.

Endpoints:
  GET  /auth/google/login    — redirect to Google OAuth2 consent screen
  GET  /auth/google/callback — handle Google callback, issue session cookie
  GET  /auth/me              — return current authenticated user
  POST /auth/logout          — clear session cookie
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from mobility_manager.config import (
    get_google_client_id,
    get_google_client_secret,
    get_google_redirect_uri,
    get_jwt_secret,
)
from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.csrf import generate_signed_state, verify_signed_state
from mobility_manager.presentation.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

_SESSION_MAX_AGE = 86400  # 24 hours
_JWT_ALGORITHM = "HS256"


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    """Redirect the browser to Google's OAuth2 consent screen."""
    state = generate_signed_state()
    # Build URL manually — avoids authlib encoding edge cases and is fully transparent.
    # prompt=select_account forces the interactive flow every time, preventing Google's
    # silent re-auth fast-path which can trigger redirect_uri_mismatch on repeated logins.
    params = urlencode({
        "response_type": "code",
        "client_id": get_google_client_id(),
        "redirect_uri": get_google_redirect_uri(),
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{params}", status_code=302)


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    """Exchange Google authorization code for session cookie."""
    if error or not code or not state:
        raise HTTPException(status_code=400, detail="OAuth2 callback error or missing parameters")

    try:
        verify_signed_state(state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": get_google_redirect_uri(),
                    "client_id": get_google_client_id(),
                    "client_secret": get_google_client_secret(),
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token: str = token_data.get("access_token", "")
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to obtain access token from Google")

            userinfo_response = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_response.raise_for_status()
            userinfo = userinfo_response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="Failed to communicate with Google") from exc

    google_sub: str = userinfo.get("sub", "")
    email: str = userinfo.get("email", "")
    display_name: str = userinfo.get("name", "")

    if not google_sub or not email:
        raise HTTPException(status_code=400, detail="Incomplete user info from Google")

    authenticate_uc = request.app.state.authenticate_google_user
    user: User = authenticate_uc.execute(
        google_sub=google_sub,
        email=email,
        display_name=display_name,
    )

    now = datetime.now(UTC)
    jwt_payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": now + timedelta(seconds=_SESSION_MAX_AGE),
    }
    session_token = jwt.encode(jwt_payload, get_jwt_secret(), algorithm=_JWT_ALGORITHM)

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=_SESSION_MAX_AGE,
    )
    return response


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)) -> JSONResponse:  # noqa: B008
    """Return the current authenticated user's profile."""
    return JSONResponse(
        content={
            "id": str(current_user.id),
            "email": current_user.email,
            "display_name": current_user.display_name,
        }
    )


@router.post("/logout", status_code=204)
async def logout() -> Response:
    """Clear the session cookie and respond with 204 No Content."""
    response = Response(status_code=204)
    response.set_cookie(
        key="session",
        value="",
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
        max_age=0,
    )
    return response
