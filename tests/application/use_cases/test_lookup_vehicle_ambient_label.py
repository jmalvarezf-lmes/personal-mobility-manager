"""
Unit tests for LookupVehicleAmbientLabel use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.use_cases.lookup_vehicle_ambient_label import (
    LookupVehicleAmbientLabel,
)
from mobility_manager.domain.ports.ambient_label_icon_repository import (
    AmbientLabelIcon,
)
from mobility_manager.domain.ports.ambient_label_lookup_port import (
    VehicleAmbientLabelResult,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.domain.value_objects.ambient_label_status import (
    AmbientLabelStatus,
)


class _FakeLookupPort:
    def __init__(self, result: VehicleAmbientLabelResult | None = None, raises: bool = False) -> None:
        self._result = result
        self._raises = raises
        self.lookup_calls: list[str] = []
        self.icon_download_calls: list[str] = []
        self.icon_download_raises = False

    def lookup(self, license_plate: str) -> VehicleAmbientLabelResult:
        self.lookup_calls.append(license_plate)
        if self._raises:
            raise RuntimeError("dgt boom")
        assert self._result is not None
        return self._result

    def download_icon(self, icon_relative_url: str) -> tuple[bytes, str]:
        self.icon_download_calls.append(icon_relative_url)
        if self.icon_download_raises:
            raise RuntimeError("icon download boom")
        return b"fake-svg-bytes", "image/svg+xml"


class _FakeLabelRepo:
    def __init__(self) -> None:
        self.upserts: list[tuple] = []

    def upsert(self, vehicle_id, label, status, last_checked_at) -> None:
        self.upserts.append((vehicle_id, label, status, last_checked_at))

    def get_by_vehicle_id(self, vehicle_id: UUID):
        return None

    def get_vehicles_needing_lookup(self, cooldown):
        return []


class _FakeIconRepo:
    def __init__(self, cached: dict[AmbientLabel, AmbientLabelIcon] | None = None) -> None:
        self._cached = cached or {}
        self.save_calls: list[tuple] = []

    def get_by_label(self, label: AmbientLabel) -> AmbientLabelIcon | None:
        return self._cached.get(label)

    def save(self, label: AmbientLabel, image_bytes: bytes, content_type: str) -> None:
        self.save_calls.append((label, image_bytes, content_type))
        self._cached[label] = AmbientLabelIcon(image_bytes=image_bytes, content_type=content_type)


def _make_use_case(lookup_port, label_repo=None, icon_repo=None) -> LookupVehicleAmbientLabel:
    return LookupVehicleAmbientLabel(
        lookup_port=lookup_port,
        label_repo=label_repo or _FakeLabelRepo(),
        icon_repo=icon_repo or _FakeIconRepo(),
    )


def test_found_label_is_persisted() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.B, icon_relative_url="/x.svg")
    lookup_port = _FakeLookupPort(result=result)
    label_repo = _FakeLabelRepo()
    uc = _make_use_case(lookup_port, label_repo=label_repo)
    vehicle_id = uuid4()

    uc.execute(vehicle_id=vehicle_id, license_plate="1234ABC")

    assert len(label_repo.upserts) == 1
    stored_vehicle_id, stored_label, stored_status, _ = label_repo.upserts[0]
    assert stored_vehicle_id == vehicle_id
    assert stored_label == AmbientLabel.B
    assert stored_status == AmbientLabelStatus.FOUND


def test_not_found_is_persisted_with_null_label() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.NOT_FOUND, label=None)
    lookup_port = _FakeLookupPort(result=result)
    label_repo = _FakeLabelRepo()
    uc = _make_use_case(lookup_port, label_repo=label_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")

    _, stored_label, stored_status, _ = label_repo.upserts[0]
    assert stored_label is None
    assert stored_status == AmbientLabelStatus.NOT_FOUND


def test_lookup_exception_is_swallowed_and_persisted_as_error() -> None:
    lookup_port = _FakeLookupPort(raises=True)
    label_repo = _FakeLabelRepo()
    uc = _make_use_case(lookup_port, label_repo=label_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")  # must not raise

    _, stored_label, stored_status, _ = label_repo.upserts[0]
    assert stored_label is None
    assert stored_status == AmbientLabelStatus.ERROR


def test_label_a_never_triggers_icon_download() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.A, icon_relative_url=None)
    lookup_port = _FakeLookupPort(result=result)
    icon_repo = _FakeIconRepo()
    uc = _make_use_case(lookup_port, icon_repo=icon_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")

    assert lookup_port.icon_download_calls == []
    assert icon_repo.save_calls == []


def test_icon_cache_miss_downloads_and_caches() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.B, icon_relative_url="/x.svg")
    lookup_port = _FakeLookupPort(result=result)
    icon_repo = _FakeIconRepo()
    uc = _make_use_case(lookup_port, icon_repo=icon_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")

    assert lookup_port.icon_download_calls == ["/x.svg"]
    assert len(icon_repo.save_calls) == 1
    assert icon_repo.save_calls[0][0] == AmbientLabel.B


def test_icon_cache_hit_skips_download() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.B, icon_relative_url="/x.svg")
    lookup_port = _FakeLookupPort(result=result)
    icon_repo = _FakeIconRepo(cached={AmbientLabel.B: AmbientLabelIcon(image_bytes=b"cached", content_type="image/svg+xml")})
    uc = _make_use_case(lookup_port, icon_repo=icon_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")

    assert lookup_port.icon_download_calls == []
    assert icon_repo.save_calls == []


def test_icon_download_failure_does_not_affect_label_persistence() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.FOUND, label=AmbientLabel.C, icon_relative_url="/x.svg")
    lookup_port = _FakeLookupPort(result=result)
    lookup_port.icon_download_raises = True
    label_repo = _FakeLabelRepo()
    uc = _make_use_case(lookup_port, label_repo=label_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")  # must not raise

    _, stored_label, stored_status, _ = label_repo.upserts[0]
    assert stored_label == AmbientLabel.C
    assert stored_status == AmbientLabelStatus.FOUND


def test_not_found_never_triggers_icon_download() -> None:
    result = VehicleAmbientLabelResult(status=AmbientLabelStatus.NOT_FOUND, label=None)
    lookup_port = _FakeLookupPort(result=result)
    icon_repo = _FakeIconRepo()
    uc = _make_use_case(lookup_port, icon_repo=icon_repo)

    uc.execute(vehicle_id=uuid4(), license_plate="1234ABC")

    assert lookup_port.icon_download_calls == []
