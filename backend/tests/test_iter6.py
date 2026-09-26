"""Iteration 6: PIN bcrypt-hashed in db.auth + PWA assets."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

API = f"{BASE}/api"


@pytest.fixture(scope="module")
def restore_pin():
    """Ensure PIN=1234 at end regardless of test outcomes."""
    yield
    # Try to change back to 1234 with common candidates
    for cur in ("1234", "4321", "5678", "9999"):
        r = requests.post(f"{API}/auth/change-pin", json={"current": cur, "new_pin": "1234"}, timeout=10)
        if r.status_code == 200:
            break
    requests.post(f"{API}/state/reset", timeout=10)


# ---- PIN leak & verify ----

def test_state_does_not_leak_pin():
    r = requests.get(f"{API}/state", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "pin" not in data
    assert "pin_hash" not in data


def test_verify_pin_correct():
    # Restore to 1234 first
    requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "1234"}, timeout=10)
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200
    assert r.json() == {"success": True}


def test_verify_pin_wrong():
    r = requests.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
    assert r.status_code == 200
    assert r.json() == {"success": False}


# ---- change-pin ----

def test_change_pin_wrong_current():
    r = requests.post(f"{API}/auth/change-pin", json={"current": "0000", "new_pin": "5678"}, timeout=10)
    assert r.status_code == 400
    assert "incorrect" in r.json().get("detail", "").lower()


def test_change_pin_invalid_new():
    r = requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "123"}, timeout=10)
    assert r.status_code == 400
    assert "4 digit" in r.json().get("detail", "").lower()

    r = requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "abcd"}, timeout=10)
    assert r.status_code == 400


def test_change_pin_success_and_survives_reset(restore_pin):
    # 1234 -> 4321
    r = requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "4321"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("success") is True

    # new works, old fails
    assert requests.post(f"{API}/auth/pin", json={"pin": "4321"}, timeout=10).json() == {"success": True}
    assert requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10).json() == {"success": False}

    # Reset state should NOT reset PIN
    rr = requests.post(f"{API}/state/reset", timeout=10)
    assert rr.status_code == 200
    assert requests.post(f"{API}/auth/pin", json={"pin": "4321"}, timeout=10).json() == {"success": True}

    # restore
    r = requests.post(f"{API}/auth/change-pin", json={"current": "4321", "new_pin": "1234"}, timeout=10)
    assert r.status_code == 200


# ---- PWA assets ----

def test_manifest_json():
    r = requests.get(f"{BASE}/manifest.json", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("display") == "standalone"
    assert "icons" in data and len(data["icons"]) > 0


def test_pwa_icons():
    for path in ("/icon-512.png", "/apple-touch-icon.png"):
        r = requests.get(f"{BASE}{path}", timeout=10)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert len(r.content) > 100


def test_index_html_pwa_meta():
    r = requests.get(f"{BASE}/", timeout=10)
    assert r.status_code == 200
    html = r.text
    assert 'rel="manifest"' in html or "rel='manifest'" in html
    assert "apple-mobile-web-app-capable" in html
    assert "apple-touch-icon" in html


# ---- Regression: prior tabs still work ----

def test_regression_away_toggle():
    r = requests.post(f"{API}/away", json={"enabled": True}, timeout=10)
    assert r.status_code == 200
    assert r.json()["away"] is True
    r = requests.post(f"{API}/away", json={"enabled": False}, timeout=10)
    assert r.json()["away"] is False


def test_regression_matrix_route():
    r = requests.post(f"{API}/matrix/route", json={"display_id": "tv_living", "source_id": "atv2"}, timeout=10)
    assert r.status_code == 200
    d = next(x for x in r.json()["displays"] if x["id"] == "tv_living")
    assert d["source"] == "atv2"


def test_regression_climate():
    r = requests.post(f"{API}/climate", json={"target_cool": 71}, timeout=10)
    assert r.status_code == 200
    assert r.json()["thermostat"]["target_cool"] == 71


def test_regression_scenes():
    r = requests.get(f"{API}/scenes", timeout=10)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert "all_off" in ids and "movie_night" in ids


def test_regression_arm():
    r = requests.post(f"{API}/security/arm", json={"enabled": True}, timeout=10)
    assert r.json()["camera"]["armed"] is True
    requests.post(f"{API}/security/arm", json={"enabled": False}, timeout=10)


def test_regression_audio_zone():
    r = requests.post(f"{API}/audio/zone", json={"zone_id": "audio_living", "volume": 42}, timeout=10)
    assert r.status_code == 200
    z = next(x for x in r.json()["audio_zones"] if x["id"] == "audio_living")
    assert z["volume"] == 42
