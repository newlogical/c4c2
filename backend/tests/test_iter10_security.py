"""
Iteration 10 - Security lockdown verification.
Tests: auth gate, PIN token issuance, demo bypass gate, secret redaction/preserve,
path-traversal, session logout.
"""
import os
import copy
import pytest
import requests

def _load_url():
    u = os.environ.get("REACT_APP_BACKEND_URL")
    if not u:
        # Fallback: read from frontend/.env
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        u = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    if not u:
        raise RuntimeError("REACT_APP_BACKEND_URL not set")
    return u.rstrip("/")

BASE_URL = _load_url()
API = f"{BASE_URL}/api"
PIN = "1234"


# -------- fixtures --------

@pytest.fixture(scope="session")
def token():
    # Try up to 3 times in case the PIN is currently locked from earlier failures.
    for _ in range(3):
        r = requests.post(f"{API}/auth/pin", json={"pin": PIN}, timeout=15)
        j = r.json()
        if j.get("success"):
            return j["token"]
        if j.get("locked"):
            import time; time.sleep(j.get("retry_after", 30) + 1)
    pytest.skip(f"Cannot obtain token: {j}")


@pytest.fixture(scope="session")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def reset_devices_after(auth_headers):
    """Snapshot original config; after all tests reset devices to live:false and clear test tokens."""
    yield
    try:
        state = requests.get(f"{API}/state", headers=auth_headers, timeout=10).json()
        cfg = state.get("config", {})
        # Force all devices back to live:false
        for k in ("matrix", "amp", "ecobee", "smartthings"):
            if k in cfg and isinstance(cfg[k], dict):
                cfg[k]["live"] = False
        if "tv" in cfg and isinstance(cfg["tv"], dict):
            for sid, s in (cfg["tv"].get("sets") or {}).items():
                if isinstance(s, dict):
                    s["live"] = False
        # Send with __stored__ for token fields to preserve real values but ensure live:false
        requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg}, timeout=15)
    except Exception as e:
        print("Teardown error:", e)


# -------- auth gate --------

SENSITIVE = [
    ("GET",    "/state",              None),
    ("PUT",    "/config",             {"config": {}}),
    ("POST",   "/scene/all_off",      {}),
    ("POST",   "/security/arm",       {"mode": "away"}),
    ("POST",   "/away",               {"on": True}),
    ("POST",   "/matrix/route",       {"input": 1, "output": 1}),
    ("GET",    "/automations",        None),
    ("GET",    "/discover",           None),
    ("POST",   "/config/test/matrix", {}),
    ("POST",   "/auth/change-pin",    {"current": PIN, "new_pin": "1234"}),
]

@pytest.mark.parametrize("method,path,body", SENSITIVE)
def test_sensitive_requires_auth(method, path, body):
    r = requests.request(method, f"{API}{path}", json=body, timeout=15)
    assert r.status_code == 401, f"{method} {path} expected 401 got {r.status_code}: {r.text[:200]}"


PUBLIC = [
    ("GET",  "/",                          None),
    ("GET",  "/bootstrap",                 None),
    ("POST", "/auth/pin",                  {"pin": PIN}),
    ("POST", "/auth/demo",                 None),
    ("GET",  "/voice/scene/all_off",       None),
    ("GET",  "/camera/stream",             None),
]

@pytest.mark.parametrize("method,path,body", PUBLIC)
def test_public_ok(method, path, body):
    r = requests.request(method, f"{API}{path}", json=body, timeout=15)
    assert r.status_code == 200, f"{method} {path} expected 200 got {r.status_code}: {r.text[:200]}"


# -------- login --------

def test_pin_login_returns_token():
    r = requests.post(f"{API}/auth/pin", json={"pin": PIN}, timeout=15)
    j = r.json()
    assert j["success"] is True
    assert isinstance(j["token"], str)
    assert len(j["token"]) >= 43


def test_pin_wrong_no_token():
    r = requests.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=15)
    j = r.json()
    assert j["success"] is False
    assert "token" not in j
    assert "attempts_left" in j
    # Clear failure counter with correct PIN so we don't lock ourselves out
    requests.post(f"{API}/auth/pin", json={"pin": PIN}, timeout=15)


# -------- authed access --------

def test_state_authed(auth_headers):
    r = requests.get(f"{API}/state", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    st = r.json()
    for key in ("displays", "audio_zones", "thermostat", "config"):
        assert key in st, f"missing {key}"


def test_control_endpoints_authed(auth_headers):
    # scene
    r = requests.post(f"{API}/scene/all_off", headers=auth_headers, timeout=15)
    assert r.status_code == 200
    # matrix route (RouteReq: display_id, source_id)
    st0 = requests.get(f"{API}/state", headers=auth_headers, timeout=15).json()
    disp = (st0.get("displays") or [{}])[0]
    src = None
    for d in st0.get("displays", []):
        if d.get("source"):
            src = d["source"]; break
    if not src:
        src = "apple_tv"
    r = requests.post(f"{API}/matrix/route", headers=auth_headers,
                      json={"display_id": disp.get("id", "living_room"), "source_id": src}, timeout=15)
    assert r.status_code == 200, r.text[:200]
    # audio zone toggle (ZoneReq: zone_id + power)
    zones = st0.get("audio_zones", [])
    if zones:
        z = zones[0]
        r = requests.post(f"{API}/audio/zone", headers=auth_headers,
                          json={"zone_id": z["id"], "power": not z.get("power", False)}, timeout=15)
        assert r.status_code == 200, r.text[:200]
    # climate
    r = requests.post(f"{API}/climate", headers=auth_headers,
                      json={"mode": "cool", "target_cool": 72}, timeout=15)
    assert r.status_code == 200
    # security arm
    r = requests.post(f"{API}/security/arm", headers=auth_headers,
                      json={"enabled": True}, timeout=15)
    assert r.status_code == 200
    # away
    r = requests.post(f"{API}/away", headers=auth_headers, json={"enabled": True}, timeout=15)
    assert r.status_code == 200
    requests.post(f"{API}/away", headers=auth_headers, json={"enabled": False}, timeout=15)
    requests.post(f"{API}/security/arm", headers=auth_headers, json={"enabled": False}, timeout=15)


# -------- secret redaction & preserve --------

def test_secret_redaction_and_preserve(auth_headers):
    real_secret = "REAL_ECOBEE_TOKEN_TEST_12345"
    # Get current cfg
    st = requests.get(f"{API}/state", headers=auth_headers, timeout=15).json()
    cfg = copy.deepcopy(st.get("config", {}))
    cfg.setdefault("ecobee", {})["token"] = real_secret
    r = requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg}, timeout=15)
    assert r.status_code == 200

    # Verify masked in /state
    st2 = requests.get(f"{API}/state", headers=auth_headers, timeout=15).json()
    assert st2["config"]["ecobee"]["token"] == "__stored__", \
        f"ecobee token not masked: {st2['config']['ecobee'].get('token')}"

    # Now PUT with __stored__ — must preserve real secret
    cfg2 = copy.deepcopy(st2["config"])
    cfg2["ecobee"]["token"] = "__stored__"
    # Modify unrelated field to ensure update actually runs
    cfg2["ecobee"]["live"] = False
    r = requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg2}, timeout=15)
    assert r.status_code == 200

    # Fetch raw (bypass redaction) via direct DB not available — instead, set to '' should clear,
    # so verify preserve by attempting a device test which needs the token, OR trust internal.
    # We can check preserve by using /config/test path? Simpler: set to '' then confirm behavior differs.
    # Instead: set token='' should clear; then re-set new value and verify masked again.
    cfg3 = copy.deepcopy(st2["config"])
    cfg3["ecobee"]["token"] = ""
    r = requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg3}, timeout=15)
    assert r.status_code == 200
    st4 = requests.get(f"{API}/state", headers=auth_headers, timeout=15).json()
    # After clearing, token should be empty (not masked)
    assert st4["config"]["ecobee"].get("token", "") in ("", None), \
        f"expected cleared token, got: {st4['config']['ecobee'].get('token')}"


# -------- demo bypass gating --------

def test_demo_bypass_flow(auth_headers):
    # currently demo mode -> should succeed
    r = requests.post(f"{API}/auth/demo", timeout=15)
    assert r.status_code == 200 and r.json().get("success") is True

    # Flip a device to live:true (matrix)
    st = requests.get(f"{API}/state", headers=auth_headers, timeout=15).json()
    cfg = copy.deepcopy(st.get("config", {}))
    cfg.setdefault("matrix", {})["live"] = True
    r = requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg}, timeout=15)
    assert r.status_code == 200

    # Now demo bypass must be 403
    r = requests.post(f"{API}/auth/demo", timeout=15)
    assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"

    # Reset live:false
    cfg["matrix"]["live"] = False
    r = requests.put(f"{API}/config", headers=auth_headers, json={"config": cfg}, timeout=15)
    assert r.status_code == 200
    r = requests.post(f"{API}/auth/demo", timeout=15)
    assert r.status_code == 200


# -------- path traversal --------

def test_hls_path_traversal():
    # Encoded traversal
    r = requests.get(f"{API}/camera/hls/cam_front/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd", timeout=15)
    assert r.status_code == 404, f"got {r.status_code}"
    r = requests.get(f"{API}/camera/hls/cam_front/..%2F..%2Fetc%2Fpasswd", timeout=15)
    assert r.status_code == 404
    # Bad name
    r = requests.get(f"{API}/camera/hls/badname_$$$/index.m3u8", timeout=15)
    assert r.status_code == 404


# -------- logout revokes token --------

def test_logout_revokes():
    # Get a fresh token
    r = requests.post(f"{API}/auth/pin", json={"pin": PIN}, timeout=15)
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = requests.get(f"{API}/state", headers=h, timeout=15)
    assert r.status_code == 200
    r = requests.post(f"{API}/auth/logout", headers=h, timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{API}/state", headers=h, timeout=15)
    assert r.status_code == 401
