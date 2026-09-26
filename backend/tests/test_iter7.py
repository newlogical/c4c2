"""Iteration 7 backend tests: PIN lockout, setup_done config, PWA assets."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://c4-controller-clone.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module", autouse=True)
def _reset_pin_lock():
    """Ensure PIN is 1234 and lock cleared before tests. Cleanup after."""
    # attempt via change-pin using default 1234; if the lock is active, we may need to wait.
    _try_change_pin("1234", "1234")
    yield
    _try_change_pin("1234", "1234")


def _try_change_pin(cur, new):
    try:
        requests.post(f"{API}/auth/change-pin", json={"current": cur, "new_pin": new}, timeout=10)
    except Exception:
        pass


# ---------- PIN lockout ----------

def test_correct_pin_unlocks():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("success") is True


def test_wrong_pin_lockout_progression():
    # ensure clean state first
    _try_change_pin("1234", "1234")
    for expected_left in [4, 3, 2, 1]:
        r = requests.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
        j = r.json()
        assert r.status_code == 200
        assert j.get("success") is False
        assert j.get("locked") is False, f"unexpected lock at attempts_left={expected_left}: {j}"
        assert j.get("attempts_left") == expected_left, j

    # 5th wrong triggers lock
    r = requests.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
    j = r.json()
    assert j.get("success") is False
    assert j.get("locked") is True
    assert j.get("attempts_left") == 0
    assert j.get("retry_after", 0) >= 25  # ~30s (some jitter for +1 rounding)


def test_correct_pin_blocked_while_locked():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    j = r.json()
    assert j.get("success") is False
    assert j.get("locked") is True
    assert j.get("retry_after", 0) > 0


def test_change_pin_clears_lock():
    r = requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "1234"}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("success") is True
    # subsequent correct pin verifies
    r2 = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r2.json().get("success") is True


def test_state_never_exposes_pin():
    r = requests.get(f"{API}/state", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "pin_hash" not in body
    j = r.json()
    assert "pin" not in j
    assert "pin_hash" not in j


# ---------- Setup_done in config ----------

def test_config_has_setup_done_field():
    r = requests.get(f"{API}/state", timeout=10)
    cfg = r.json().get("config") or {}
    assert "setup_done" in cfg, cfg


def test_setup_done_persists_true():
    r = requests.put(f"{API}/config", json={"config": {"setup_done": True}}, timeout=10)
    assert r.status_code == 200
    r2 = requests.get(f"{API}/state", timeout=10)
    assert r2.json()["config"]["setup_done"] is True


def test_reset_sets_setup_done_false():
    r = requests.post(f"{API}/state/reset", timeout=10)
    assert r.status_code == 200
    assert r.json()["config"]["setup_done"] is False


# ---------- PWA assets ----------

@pytest.mark.parametrize("path", ["/manifest.json", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"])
def test_pwa_asset_exists(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=10)
    assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_manifest_structure():
    r = requests.get(f"{BASE_URL}/manifest.json", timeout=10)
    j = r.json()
    assert j.get("display") == "standalone"
    icons = j.get("icons", [])
    assert any(i.get("purpose") == "maskable" and "512" in str(i.get("sizes", "")) for i in icons), icons
    assert any("192" in str(i.get("sizes", "")) for i in icons)
    assert any("512" in str(i.get("sizes", "")) for i in icons)


def test_index_html_has_pwa_tags():
    r = requests.get(f"{BASE_URL}/", timeout=10)
    html = r.text
    assert 'rel="manifest"' in html
    assert "apple-touch-startup-image" in html
