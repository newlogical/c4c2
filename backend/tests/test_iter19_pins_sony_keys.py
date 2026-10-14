"""Iteration 19 backend tests: /api/scenes/{id}/pin and /api/display/tvkey (Sony)."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://c4-controller-clone.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    if not data.get("success"):
        # try demo
        r = requests.post(f"{BASE_URL}/api/auth/demo", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
    assert data.get("success"), data
    return data["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Pin scene ----------------

class TestPinScene:
    def test_pin_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/scenes/good_night/pin", json={"pinned": True}, timeout=10)
        assert r.status_code == 401

    def test_pin_unknown_404(self, auth):
        r = requests.post(f"{BASE_URL}/api/scenes/does_not_exist/pin", json={"pinned": True}, headers=auth, timeout=10)
        assert r.status_code == 404

    def test_default_contains_living_preset(self, auth):
        r = requests.get(f"{BASE_URL}/api/state", headers=auth, timeout=10)
        assert r.status_code == 200
        assert "preset_living_tv_sound" in (r.json().get("pinned_scenes") or [])

    def test_pin_builtin_good_night_then_unpin(self, auth):
        r = requests.post(f"{BASE_URL}/api/scenes/good_night/pin", json={"pinned": True}, headers=auth, timeout=10)
        assert r.status_code == 200
        pins = r.json()["pinned_scenes"]
        assert "good_night" in pins
        # No duplicates when pinning again
        r = requests.post(f"{BASE_URL}/api/scenes/good_night/pin", json={"pinned": True}, headers=auth, timeout=10)
        assert r.status_code == 200
        pins = r.json()["pinned_scenes"]
        assert pins.count("good_night") == 1
        # Unpin
        r = requests.post(f"{BASE_URL}/api/scenes/good_night/pin", json={"pinned": False}, headers=auth, timeout=10)
        assert r.status_code == 200
        assert "good_night" not in r.json()["pinned_scenes"]

    def test_delete_custom_preset_removes_from_pinned(self, auth):
        # Create preset
        payload = {"name": "TEST_pin_del", "icon": "Sparkles",
                   "actions": [{"type": "tv_power", "target": "tv_office", "value": False}]}
        r = requests.post(f"{BASE_URL}/api/presets", json=payload, headers=auth, timeout=10)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        # Pin it
        r = requests.post(f"{BASE_URL}/api/scenes/{pid}/pin", json={"pinned": True}, headers=auth, timeout=10)
        assert r.status_code == 200
        assert pid in r.json()["pinned_scenes"]
        # Delete preset
        r = requests.delete(f"{BASE_URL}/api/scenes/{pid}", headers=auth, timeout=10)
        assert r.status_code == 200
        # Confirm removed from pinned
        r = requests.get(f"{BASE_URL}/api/state", headers=auth, timeout=10)
        assert pid not in (r.json().get("pinned_scenes") or [])

    def test_final_restore_only_living_preset(self, auth):
        """End state cleanup: pinned_scenes == ['preset_living_tv_sound']."""
        r = requests.get(f"{BASE_URL}/api/state", headers=auth, timeout=10)
        pins = list(r.json().get("pinned_scenes") or [])
        for p in pins:
            if p != "preset_living_tv_sound":
                requests.post(f"{BASE_URL}/api/scenes/{p}/pin", json={"pinned": False}, headers=auth, timeout=10)
        if "preset_living_tv_sound" not in pins:
            requests.post(f"{BASE_URL}/api/scenes/preset_living_tv_sound/pin",
                          json={"pinned": True}, headers=auth, timeout=10)
        r = requests.get(f"{BASE_URL}/api/state", headers=auth, timeout=10)
        assert r.json()["pinned_scenes"] == ["preset_living_tv_sound"]


# ---------------- Sony TV key ----------------

SONY_KEYS = [
    "KEY_1", "KEY_2", "KEY_3", "KEY_4", "KEY_5", "KEY_6", "KEY_7", "KEY_8", "KEY_9", "KEY_0",
    "KEY_BACK", "KEY_INPUT", "KEY_GUIDE", "KEY_PLAY", "KEY_PAUSE", "KEY_NETFLIX", "KEY_YOUTUBE",
    "KEY_CHUP", "KEY_CHDOWN", "KEY_OPTIONS", "KEY_HOME", "KEY_ENTER",
    "KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT",
    "KEY_VOLUP", "KEY_VOLDOWN", "KEY_MUTE",
]


class TestTvKey:
    def test_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/display/tvkey",
                          json={"source_id": "tv_office", "key": "KEY_HOME"}, timeout=10)
        assert r.status_code == 401

    def test_unknown_display_404(self, auth):
        r = requests.post(f"{BASE_URL}/api/display/tvkey",
                          json={"source_id": "tv_nope", "key": "KEY_HOME"}, headers=auth, timeout=10)
        assert r.status_code == 404

    @pytest.mark.parametrize("key", SONY_KEYS)
    def test_each_key_logs_ircc_simulated(self, auth, key):
        r = requests.post(f"{BASE_URL}/api/display/tvkey",
                          json={"source_id": "tv_office", "key": key}, headers=auth, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        # First log entry should be this IRCC call
        top = data["command_log"][0]
        assert top["driver"] == "SonyBravia"
        assert top["command"] == f"IRCC {key}"
        # Not live -> simulated
        assert top["status"] == "simulated"
