"""Iteration 15 — PTZ (presets/patrol/move) + Apple TV pairing coverage."""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    for line in Path('/app/frontend/.env').read_text().splitlines():
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
            break
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---- auth gate ----
@pytest.mark.parametrize("method,path,body", [
    ("GET", "/ptz/presets", None),
    ("POST", "/ptz/goto", {"slot": 0}),
    ("POST", "/ptz/patrol", {"start": True, "slot": 0}),
    ("POST", "/ptz/move", {"pan": 0}),
    ("POST", "/appletv/atv1/pair/start", {"protocol": "companion"}),
])
def test_requires_auth(method, path, body):
    r = requests.request(method, f"{API}{path}", json=body, timeout=10)
    assert r.status_code == 401, f"{method} {path} -> {r.status_code}"


# ---- demo-mode PTZ ----
def test_ptz_presets_default(auth):
    r = requests.get(f"{API}/ptz/presets", headers=auth, timeout=10)
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert presets[0] == {"slot": -1, "name": "Home"}
    names = [p["name"] for p in presets[1:]]
    assert names == ["Preset 1", "Preset 2", "Preset 3"]
    assert [p["slot"] for p in presets[1:]] == [0, 1, 2]


def test_ptz_goto_simulated_and_logged(auth):
    r = requests.post(f"{API}/ptz/goto", headers=auth, json={"slot": 0}, timeout=10)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "status": "simulated"}
    # verify logged
    s = requests.get(f"{API}/state", headers=auth, timeout=10).json()
    log = s.get("command_log", [])
    assert any(e.get("driver") == "UniFiPTZ" and e.get("status") == "simulated" for e in log[:5])


def test_ptz_goto_bad_slot(auth):
    r = requests.post(f"{API}/ptz/goto", headers=auth, json={"slot": 20}, timeout=10)
    assert r.status_code == 400


def test_ptz_patrol_start_stop(auth):
    r = requests.post(f"{API}/ptz/patrol", headers=auth, json={"start": True, "slot": 0}, timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "simulated"
    r2 = requests.post(f"{API}/ptz/patrol", headers=auth, json={"start": False}, timeout=10)
    assert r2.status_code == 200 and r2.json()["status"] == "simulated"


def test_ptz_move_quiet_vs_stop(auth):
    # moving: quiet (not logged)
    before = requests.get(f"{API}/state", headers=auth, timeout=10).json().get("command_log", [])
    r = requests.post(f"{API}/ptz/move", headers=auth, json={"pan": 500}, timeout=10)
    assert r.status_code == 200 and r.json()["status"] == "simulated"
    after = requests.get(f"{API}/state", headers=auth, timeout=10).json().get("command_log", [])
    # The 'move' (non-stop) entry should NOT be at the head
    assert not (after and after[0].get("note", "").startswith("PTZ move")), f"move was logged: {after[0]}"
    # stop logs it
    r2 = requests.post(f"{API}/ptz/move", headers=auth, json={}, timeout=10)
    assert r2.status_code == 200
    after2 = requests.get(f"{API}/state", headers=auth, timeout=10).json().get("command_log", [])
    assert after2 and after2[0].get("note") == "PTZ stop"


# ---- preset names update ----
def test_preset_names_from_config(auth):
    try:
        requests.put(f"{API}/config", headers=auth,
                     json={"config": {"camera": {"ptz_presets": "Door, Hallway"}}}, timeout=10)
        r = requests.get(f"{API}/ptz/presets", headers=auth, timeout=10)
        names = [p["name"] for p in r.json()["presets"]]
        assert names == ["Home", "Door", "Hallway"]
    finally:
        requests.put(f"{API}/config", headers=auth,
                     json={"config": {"camera": {"ptz_presets": "Preset 1, Preset 2, Preset 3"}}}, timeout=10)


# ---- live PTZ (unreachable) ----
def test_ptz_live_unreachable(auth):
    try:
        r0 = requests.put(f"{API}/config", headers=auth,
                          json={"config": {"camera": {"live": True, "protect_api_key": "k"}}}, timeout=10)
        assert r0.status_code == 200
        # verify key is masked
        assert r0.json()["config"]["camera"]["protect_api_key"] == "__stored__"
        r = requests.post(f"{API}/ptz/goto", headers=auth, json={"slot": 0}, timeout=20)
        assert r.status_code == 424, r.text
        detail = r.json().get("detail", "")
        assert "192.168.0.166" in detail, f"detail={detail!r}"
    finally:
        requests.put(f"{API}/config", headers=auth,
                     json={"config": {"camera": {"live": False, "protect_api_key": ""}}}, timeout=10)


# ---- Apple TV pairing ----
def test_atv_pair_bogus_protocol(auth):
    r = requests.post(f"{API}/appletv/atv1/pair/start", headers=auth,
                      json={"protocol": "bogus"}, timeout=10)
    assert r.status_code == 400


def test_atv_pair_finish_without_start(auth):
    r = requests.post(f"{API}/appletv/atv1/pair/finish", headers=auth,
                      json={"protocol": "companion", "pin": "1234"}, timeout=10)
    assert r.status_code == 400
    assert "Start pairing first" in r.json().get("detail", "")


def test_atv_pair_start_unreachable(auth):
    r = requests.post(f"{API}/appletv/atv1/pair/start", headers=auth,
                      json={"protocol": "companion"}, timeout=20)
    assert r.status_code == 404, r.text
    detail = r.json().get("detail", "")
    assert "192.168.0.145" in detail, f"detail={detail!r}"
