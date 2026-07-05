"""
Unit tests for SerTicketProviderConnectFactory.
"""

from uuid import uuid4

from mobility_manager.presentation.api.factories import SerTicketProviderConnectFactory
from mobility_manager.presentation.api.schemas import ConnectElParkingRequest


def test_factory_injects_stable_uid_and_fixed_model() -> None:
    user_id = uuid4()
    body = ConnectElParkingRequest(provider="elparking", email="alice@example.com", password="s3cr3t")

    credentials = SerTicketProviderConnectFactory.build(body, user_id)

    assert credentials.data["email"] == "alice@example.com"
    assert credentials.data["password"] == "s3cr3t"
    assert credentials.data["uid"] == str(user_id)
    assert credentials.data["model"] == "personal-mobility-manager-server"


def test_factory_uid_is_stable_across_calls_for_same_user() -> None:
    user_id = uuid4()
    body = ConnectElParkingRequest(provider="elparking", email="alice@example.com", password="s3cr3t")

    first = SerTicketProviderConnectFactory.build(body, user_id)
    second = SerTicketProviderConnectFactory.build(body, user_id)

    assert first.data["uid"] == second.data["uid"] == str(user_id)
