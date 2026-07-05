"""
Infrastructure: PostgresUserSerProviderConfigRepository.

Stores per-user, per-provider SER sessions: JSON-serialised payload
encrypted via Fernet, exactly mirroring PostgresVehicleConfigRepository's
treatment of Toyota's credential payload — but keyed by (user_id, provider)
since SER provider accounts are personal, not per-vehicle.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)
from mobility_manager.infrastructure.crypto import decrypt, encrypt
from mobility_manager.infrastructure.orm.tables import user_ser_provider_configs_table


class PostgresUserSerProviderConfigRepository(UserSerProviderConfigRepository):
    """
    PostgreSQL-backed per-user SER provider session repository.

    Args:
        engine: SQLAlchemy engine.
        encryption_key: Fernet key bytes. Required at call time to save/find sessions.
            Pass None if no encryption key is configured yet (e.g. deployments that
            haven't enabled any SER provider) — save/find will raise RuntimeError.
    """

    def __init__(self, engine: Engine, encryption_key: bytes | None = None) -> None:
        self._engine = engine
        self._encryption_key = encryption_key

    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        """
        Serialise session.data to JSON, encrypt it, and upsert the row for (user_id, provider).

        Raises:
            RuntimeError: If encryption_key was not provided at construction.
        """
        if self._encryption_key is None:
            raise RuntimeError("encryption_key is required to save a SER provider session but was not provided")
        ciphertext = encrypt(session.data, self._encryption_key)
        now = datetime.now(UTC)

        stmt = pg_insert(user_ser_provider_configs_table).values(
            user_id=user_id,
            provider=provider,
            encrypted_payload=ciphertext,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "provider"],
            set_={"encrypted_payload": ciphertext, "updated_at": now},
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        """
        Return the decrypted, deserialised session for (user_id, provider), or None if absent.

        Raises:
            RuntimeError: If encryption_key was not provided at construction.
        """
        if self._encryption_key is None:
            raise RuntimeError("encryption_key is required to read a SER provider session but was not provided")
        with self._engine.connect() as conn:
            row = conn.execute(
                select(user_ser_provider_configs_table.c.encrypted_payload).where(
                    user_ser_provider_configs_table.c.user_id == user_id,
                    user_ser_provider_configs_table.c.provider == provider,
                )
            ).fetchone()

        if row is None:
            return None

        data = decrypt(row.encrypted_payload, self._encryption_key)
        return SerProviderSession(data=data)

    def delete(self, user_id: UUID, provider: str) -> None:
        """Remove the stored session for (user_id, provider), if present. Idempotent — never raises if absent."""
        stmt = sa_delete(user_ser_provider_configs_table).where(
            user_ser_provider_configs_table.c.user_id == user_id,
            user_ser_provider_configs_table.c.provider == provider,
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)

    def list_connected_providers(self, user_id: UUID) -> list[str]:
        """Return the provider names for which `user_id` has a stored session."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(user_ser_provider_configs_table.c.provider).where(
                    user_ser_provider_configs_table.c.user_id == user_id,
                )
            ).fetchall()
        return [row.provider for row in rows]
