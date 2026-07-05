"""
Presentation: SER ticket providers API router.

Endpoints:
  POST /ser-ticket-providers/connections — connect the current user's SER
    ticket provider account (e.g. ElParking) by submitting credentials.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
    SerTicketProviderNotFoundError,
)
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.factories import SerTicketProviderConnectFactory
from mobility_manager.presentation.api.schemas import ConnectSerTicketProviderRequest

router = APIRouter(prefix="/ser-ticket-providers", tags=["ser-ticket-providers"])


@router.post("/connections", status_code=204)
def create_connection(
    request: Request,
    body: ConnectSerTicketProviderRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """
    Connect the authenticated user's account to a SER ticket provider.

    Returns 204 No Content on success. Nothing flows back to the caller —
    the resulting session stays server-side.
    """
    credentials = SerTicketProviderConnectFactory.build(body, current_user.id)

    use_case = request.app.state.connect_ser_ticket_provider

    try:
        use_case.execute(user_id=current_user.id, provider=body.provider, credentials=credentials)
    except SerProviderAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SerProviderApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SerTicketProviderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(status_code=204)
