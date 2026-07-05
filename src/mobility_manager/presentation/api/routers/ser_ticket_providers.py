"""
Presentation: SER ticket providers API router.

Endpoints:
  POST /ser-ticket-providers/connections — connect the current user's SER
    ticket provider account (e.g. ElParking) by submitting credentials.
  GET /ser-ticket-providers/connections — list the providers the current
    user has connected.
  DELETE /ser-ticket-providers/connections/{provider} — disconnect a
    provider, attempting a best-effort provider-side logout.
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
from mobility_manager.presentation.api.schemas import (
    ConnectSerTicketProviderRequest,
    DisconnectSerTicketProviderResponse,
    SerTicketProviderConnectionsResponse,
)

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


@router.get("/connections", response_model=SerTicketProviderConnectionsResponse)
def list_connections(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> SerTicketProviderConnectionsResponse:
    """List the SER ticket providers the authenticated user has connected."""
    use_case = request.app.state.list_ser_ticket_provider_connections

    providers = use_case.execute(current_user.id)

    return SerTicketProviderConnectionsResponse(providers=providers)


@router.delete("/connections/{provider}", response_model=DisconnectSerTicketProviderResponse)
def disconnect_connection(
    request: Request,
    provider: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> DisconnectSerTicketProviderResponse:
    """
    Disconnect the authenticated user's connection to `provider`.

    Always returns 200 OK — never 204 — because the response body carries
    the `logout_succeeded` soft-failure signal: the local session is always
    removed, but the provider-side logout may not have been confirmed.
    """
    use_case = request.app.state.disconnect_ser_ticket_provider

    logout_succeeded = use_case.execute(user_id=current_user.id, provider=provider)

    return DisconnectSerTicketProviderResponse(logout_succeeded=logout_succeeded)
