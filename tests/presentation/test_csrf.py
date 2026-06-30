"""
Unit tests for csrf.py — signed OAuth2 state generation and verification.
"""

import time
from unittest.mock import patch

import pytest

from mobility_manager.presentation.api.csrf import generate_signed_state, verify_signed_state


class TestGenerateSignedState:
    def test_returns_non_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        state = generate_signed_state()
        assert isinstance(state, str)
        assert len(state) > 0

    def test_two_states_are_different(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        s1 = generate_signed_state()
        s2 = generate_signed_state()
        assert s1 != s2


class TestVerifySignedState:
    def test_valid_state_does_not_raise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        state = generate_signed_state()
        verify_signed_state(state)  # should not raise

    def test_tampered_state_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        state = generate_signed_state()
        tampered = state[:-4] + "XXXX"
        with pytest.raises(ValueError):
            verify_signed_state(tampered)

    def test_expired_state_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        # Generate a state, then freeze time 6 minutes in the future
        state = generate_signed_state()
        future_time = time.time() + 301  # 5 minutes + 1 second
        with patch("itsdangerous.timed.time") as mock_time:
            mock_time.return_value = future_time
            with pytest.raises(ValueError, match="expired"):
                verify_signed_state(state)

    def test_wrong_secret_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "secret-a")
        state = generate_signed_state()
        monkeypatch.setenv("JWT_SECRET", "secret-b")
        with pytest.raises(ValueError):
            verify_signed_state(state)

    def test_garbage_string_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", "test-secret-key")
        with pytest.raises(ValueError):
            verify_signed_state("not-a-valid-token")
