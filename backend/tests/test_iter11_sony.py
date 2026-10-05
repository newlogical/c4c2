"""Iter 11: Sony Bravia TV driver replacement + lock-screen QR regression tests.
Covers: auth regression, config shape (psk, no smartthings), PSK masking,
Sony driver demo-mode log entries, and /config/test/tv."""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    assert isinstance(data.get("token"), str) and len(data["token"]) > 10
    return data["token"]


@pytest.fixture(scope="module")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# --- Auth regression ---------------------------------------------------------

def test_state_requires_auth():
    r = requests.get(f"{API}/state", timeout=10)
    assert r.status_code == 401


def test_put_config_requires_auth():
    r = requests.put(f"{API}/config", json={"config": {}}, timeout=10)
    assert r.status_code == 401


def test_bad_pin():
    r = requests.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
    # may be 200 w/ success:false; just verify not issuing a token
    assert r.status_code == 200
    assert r.json().get("success") is False or "token" not in r.json()


# --- Config shape ------------------------------------------------------------

def test_config_tv_sets_shape(client):
    r = client.get(f"{API}/state", timeout=10)
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert "smartthings" not in cfg, "smartthings must be removed"
    tv = cfg["tv"]
    assert "sets" in tv
    for tv_id, s in tv["sets"].items():
        assert set(["ip", "mac", "hdmi_input", "psk"]).issubset(s.keys()), f"{tv_id} keys={s.keys()}"
        assert "token" not in s, f"{tv_id} still has legacy 'token'"


# --- PSK masking + preserve on round trip -----------------------------------

def test_psk_mask_and_preserve(client):
    secret = "SUPER_SECRET_PSK_ABC123"
    # set PSK
    r = client.put(f"{API}/config", json={"config": {"tv": {"sets": {"tv_living": {"psk": secret}}}}}, timeout=10)
    assert r.status_code == 200
    # read -> must be masked
    r = client.get(f"{API}/state", timeout=10)
    psk = r.json()["config"]["tv"]["sets"]["tv_living"]["psk"]
    assert psk == "__stored__", f"expected mask, got {psk!r}"
    # resend mask -> must preserve
    r = client.put(f"{API}/config", json={"config": {"tv": {"sets": {"tv_living": {"psk": "__stored__", "hdmi_input": 2}}}}}, timeout=10)
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg["tv"]["sets"]["tv_living"]["psk"] == "__stored__"
    assert cfg["tv"]["sets"]["tv_living"]["hdmi_input"] == 2
    # cleanup
    client.put(f"{API}/config", json={"config": {"tv": {"live": False, "sets": {"tv_living": {"psk": "", "hdmi_input": 1, "ip": "", "mac": ""}}}}}, timeout=10)


# --- Sony driver log entries (demo / simulated) ------------------------------

def _sony_log_entry(log, note_sub):
    for e in log:
        if e.get("driver") == "SonyBravia" and note_sub in (e.get("note") or ""):
            return e
    return None


def test_display_power_sony_log(client):
    r = client.post(f"{API}/display/power", json={"display_id": "tv_living", "power": True}, timeout=10)
    assert r.status_code == 200
    log = r.json()["command_log"]
    entry = _sony_log_entry(log, "power ON (Wake-on-LAN)")
    assert entry is not None, f"No SonyBravia WoL entry in {[e.get('note') for e in log[:5]]}"
    assert entry["status"] == "simulated"


def test_display_tvvolume_sony_log(client):
    r = client.post(f"{API}/display/tvvolume", json={"display_id": "tv_living", "volume": 42}, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["tv_volume"] == 42
    entry = _sony_log_entry(data["command_log"], "volume -> 42%")
    assert entry is not None
    assert entry["status"] == "simulated"


def test_display_tvkey_sony_log(client):
    r = client.post(f"{API}/display/tvkey", json={"source_id": "tv_living", "key": "KEY_MUTE"}, timeout=10)
    assert r.status_code == 200
    entry = _sony_log_entry(r.json()["command_log"], "KEY_MUTE")
    assert entry is not None
    assert entry["command"] == "IRCC KEY_MUTE"


# --- Test connection ---------------------------------------------------------

def test_config_test_tv_demo(client):
    r = client.post(f"{API}/config/test/tv", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "demo" in body["detail"].lower()


def test_config_test_smartthings_removed(client):
    r = client.post(f"{API}/config/test/smartthings", timeout=10)
    # middleware passes through; endpoint returns ok:false "No test available"
    assert r.status_code == 200
    assert r.json()["ok"] is False
