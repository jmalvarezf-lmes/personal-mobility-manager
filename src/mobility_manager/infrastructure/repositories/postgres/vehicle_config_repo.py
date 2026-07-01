"""
Infrastructure: PostgresVehicleConfigRepository.

Stores per-vehicle configuration:
- Toyota: JSON-serialised credentials encrypted via Fernet.
- Generic: location_token stored as cleartext (indexed for push-endpoint dispatch).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine

from mobility_manager.domain.exceptions import VehicleConfigNotFoundError
from mobility_manager.domain.ports.vehicle_config_repository import (
    VehicleConfigRepository,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
from mobility_manager.infrastructure.crypto import decrypt, encrypt
from mobility_manager.infrastructure.orm.tables import vehicle_configs_table


class PostgresVehicleConfigRepository(VehicleConfigRepository):
    """
    PostgreSQL-backed vehicle config repository.

    Args:
        engine: SQLAlchemy engine.
        encryption_key: Fernet key bytes. Required when Toyota vehicles are used.
            Pass None if Toyota is not enabled (generic-only deployments).
    """

    def __init__(self, engine: Engine, encryption_key: bytes | None = None) -> None:
        self._engine = engine
        self._encryption_key = encryption_key

    # ------------------------------------------------------------------
    # Toyota
    # ------------------------------------------------------------------

    def save_toyota_config(self, vehicle_id: UUID, config: ToyotaConfig) -> None:
        """
        Serialise ToyotaConfig to JSON, encrypt it, and upsert the row.

        Raises:
            RuntimeError: If encryption_key was not provided at construction.
        """
        if self._encryption_key is None:
            raise RuntimeError("encryption_key is required to save Toyota config but was not provided")
        payload = {
            "username": config.username,
            "password": config.password,
            "locale": config.locale,
            "vin": config.vin,
        }
        ciphertext = encrypt(payload, self._encryption_key)
        now = datetime.now(UTC)

        with self._engine.begin() as conn:
            conn.execute(
                vehicle_configs_table.insert().values(
                    vehicle_id=vehicle_id,
                    brand=Brand.TOYOTA.value,
                    encrypted_payload=ciphertext,
                    location_token=None,
                    updated_at=now,
                )
            )

    def get_toyota_config(self, vehicle_id: UUID) -> ToyotaConfig:
        """
        Retrieve and decrypt the Toyota config for the given vehicle.

        Raises:
            VehicleConfigNotFoundError: If no Toyota config exists for vehicle_id.
            RuntimeError: If encryption_key was not provided at construction.
        """
        if self._encryption_key is None:
            raise RuntimeError("encryption_key is required to read Toyota config but was not provided")
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_configs_table).where(
                    vehicle_configs_table.c.vehicle_id == vehicle_id,
                    vehicle_configs_table.c.brand == Brand.TOYOTA.value,
                )
            ).fetchone()

        if row is None or row.encrypted_payload is None:
            raise VehicleConfigNotFoundError(f"No Toyota config found for vehicle {vehicle_id}")

        data = decrypt(row.encrypted_payload, self._encryption_key)
        return ToyotaConfig(
            username=data["username"],
            password=data["password"],
            locale=data["locale"],
            vin=data["vin"],
        )

    # ------------------------------------------------------------------
    # Generic
    # ------------------------------------------------------------------

    def save_generic_config(self, vehicle_id: UUID, config: GenericConfig) -> None:
        """Store the generic location_token as cleartext."""
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            conn.execute(
                vehicle_configs_table.insert().values(
                    vehicle_id=vehicle_id,
                    brand=Brand.GENERIC.value,
                    encrypted_payload=None,
                    location_token=config.location_token,
                    updated_at=now,
                )
            )

    def get_generic_config(self, vehicle_id: UUID) -> GenericConfig | None:
        """Return the generic config for the given vehicle, or None if not found."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_configs_table).where(
                    vehicle_configs_table.c.vehicle_id == vehicle_id,
                    vehicle_configs_table.c.brand == Brand.GENERIC.value,
                )
            ).fetchone()
        if row is None or row.location_token is None:
            return None
        return GenericConfig(location_token=row.location_token)

    def find_vehicle_by_token(self, token: str) -> UUID | None:
        """
        Resolve a push-endpoint token to a vehicle UUID using the indexed column.

        Returns None if no match is found.
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                select(vehicle_configs_table.c.vehicle_id).where(vehicle_configs_table.c.location_token == token)
            ).fetchone()
        if row is None:
            return None
        return UUID(str(row.vehicle_id))

    def update_toyota_config(self, vehicle_id: UUID, config: ToyotaConfig) -> None:
        """
        Re-encrypt updated Toyota credentials and write them back.

        Raises:
            RuntimeError: If encryption_key was not provided at construction.
        """
        if self._encryption_key is None:
            raise RuntimeError("encryption_key is required to update Toyota config but was not provided")
        payload = {
            "username": config.username,
            "password": config.password,
            "locale": config.locale,
            "vin": config.vin,
        }
        ciphertext = encrypt(payload, self._encryption_key)
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            conn.execute(
                vehicle_configs_table.update()
                .where(
                    vehicle_configs_table.c.vehicle_id == vehicle_id,
                    vehicle_configs_table.c.brand == Brand.TOYOTA.value,
                )
                .values(encrypted_payload=ciphertext, updated_at=now)
            )
