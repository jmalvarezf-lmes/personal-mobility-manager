"""Unit tests for ETRS89 UTM Zone 30N → WGS84 coordinate reprojection."""

import pytest
from pyproj import Transformer

# Known Madrid reference point: Puerta del Sol
# ETRS89 UTM Zone 30N (EPSG:25830): X=440594 m, Y=4474469 m
# In the Madrid callejero CSV these are stored in centimetres:
#   X_cm = 44059400, Y_cm = 447446900
# Expected WGS84: lat≈40.4168, lng≈-3.7038
_PUERTA_DEL_SOL_X_CM = 44059400
_PUERTA_DEL_SOL_Y_CM = 447446900
_PUERTA_DEL_SOL_X = _PUERTA_DEL_SOL_X_CM / 100.0  # 440594.0 m
_PUERTA_DEL_SOL_Y = _PUERTA_DEL_SOL_Y_CM / 100.0  # 4474469.0 m
_EXPECTED_LAT = 40.4168
_EXPECTED_LNG = -3.7038
_TOLERANCE = 0.005  # degrees (~500 m) — input UTM coords are approximate


def test_cm_to_metres_conversion() -> None:
    """Centimetre values from the CSV divide by 100 to give UTM metres."""
    assert pytest.approx(440594.0) == _PUERTA_DEL_SOL_X
    assert pytest.approx(4474469.0) == _PUERTA_DEL_SOL_Y


def test_puerta_del_sol_reprojection() -> None:
    """Reprojects known Puerta del Sol UTM coords and checks WGS84 result."""
    transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    lng, lat = transformer.transform(_PUERTA_DEL_SOL_X, _PUERTA_DEL_SOL_Y)

    assert abs(lat - _EXPECTED_LAT) < _TOLERANCE, (
        f"Latitude mismatch: got {lat}, expected {_EXPECTED_LAT} ±{_TOLERANCE}"
    )
    assert abs(lng - _EXPECTED_LNG) < _TOLERANCE, (
        f"Longitude mismatch: got {lng}, expected {_EXPECTED_LNG} ±{_TOLERANCE}"
    )


def test_reprojection_result_is_in_madrid_bbox() -> None:
    """Verifies that reprojected coordinates fall within the Madrid bounding box."""
    transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    lng, lat = transformer.transform(_PUERTA_DEL_SOL_X, _PUERTA_DEL_SOL_Y)

    assert 39.8 <= lat <= 41.2, f"Latitude {lat} outside Madrid bbox"
    assert -4.6 <= lng <= -2.9, f"Longitude {lng} outside Madrid bbox"
