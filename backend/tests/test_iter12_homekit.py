"""Iter 12: Ecobee HomeKit (local HAP/IP) replacing Ecobee cloud API."""
import os
import time
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
PIN = "1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/pin", json={"pin": PIN}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    return data["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# -- state shape -------------------------------------------------------------
def test_state_ecobee_fields(auth):
    r = requests.get(f"{BASE}/api/state", headers=auth, timeout=10)
    assert r.status_code == 200
    ec = r.json()["config"]["ecobee"]
    assert ec["ip"] == "192.168.0.222"
    assert ec["mac"] == "44:61:32:DF:C2:A9"
    assert ec["paired"] is False
    assert "token" not in ec
    assert "thermostat_id" not in ec


# -- homekit/pair auth + validation -----------------------------------------
def test_pair_requires_auth():
    r = requests.post(f"{BASE}/api/homekit/pair", json={"code": "12345678"}, timeout=10)
    assert r.status_code == 401


def test_pair_bad_code_length(auth):
    r = requests.post(f"{BASE}/api/homekit/pair", headers=auth, json={"code": "12"}, timeout=15)
    assert r.status_code == 400
    assert "8 digits" in r.json().get("detail", "")


def test_pair_valid_format_no_accessory(auth):
    # cloud cannot reach LAN -> aiohomekit discover will timeout
    t0 = time.time()
    r = requests.post(f"{BASE}/api/homekit/pair", headers=auth, json={"code": "111-22-333"}, timeout=60)
    elapsed = time.time() - t0
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "No HomeKit accessory advertising at 192.168.0.222" in detail
    # ~10s discover loop (20 iters * 0.5s)
    assert elapsed >= 5, f"Expected ~10s wait, got {elapsed}"


# -- climate/refresh when unpaired ------------------------------------------
def test_climate_refresh_not_paired(auth):
    r = requests.post(f"{BASE}/api/climate/refresh", headers=auth, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["live"] is False
    assert "state" in data


def test_homekit_unpair(auth):
    r = requests.delete(f"{BASE}/api/homekit/pair", headers=auth, timeout=10)
    assert r.status_code == 200
    ec = r.json()["config"]["ecobee"]
    assert ec["paired"] is False


# -- climate updates still simulate in DEMO ---------------------------------
def test_climate_mode_and_targets(auth):
    r = requests.post(f"{BASE}/api/climate", headers=auth,
                      json={"mode": "cool", "target_heat": 68, "target_cool": 74, "fan": "auto"}, timeout=10)
    assert r.status_code == 200
    s = r.json()
    assert s["thermostat"]["mode"] == "cool"
    assert s["thermostat"]["target_heat"] == 68
    assert s["thermostat"]["target_cool"] == 74
    assert s["thermostat"]["fan"] == "auto"
    log = s["command_log"]
    ec_entries = [e for e in log if e.get("driver") == "Ecobee"]
    assert ec_entries, "expected Ecobee log entries"
    for e in ec_entries[:3]:
        assert e["transport"] == "HomeKit HAP/IP (LAN)"
        assert e["status"] == "simulated"


def test_good_night_scene_logs_cool_mode(auth):
    r = requests.post(f"{BASE}/api/scene/good_night", headers=auth, timeout=10)
    assert r.status_code == 200
    s = r.json()
    log = s["command_log"]
    # most recent entries first; look for an Ecobee set_mode cool
    mode_cool = [e for e in log if e.get("driver") == "Ecobee" and "mode = cool" in e.get("note", "")]
    assert mode_cool, "expected Ecobee set_mode cool entry from good_night"
    assert mode_cool[0]["transport"] == "HomeKit HAP/IP (LAN)"


# -- /config/test/ecobee live but not paired --------------------------------
def test_config_test_ecobee_live_not_paired(auth):
    # Enable ecobee live (keep paired false)
    cfg = {"ecobee": {"live": True, "paired": False}}
    r = requests.put(f"{BASE}/api/config", headers=auth, json={"config": cfg}, timeout=10)
    assert r.status_code == 200
    try:
        r = requests.post(f"{BASE}/api/config/test/ecobee", headers=auth, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is False
        assert "Not paired" in data["detail"]
    finally:
        # Teardown: restore demo (live false)
        requests.put(f"{BASE}/api/config", headers=auth,
                     json={"config": {"ecobee": {"live": False, "paired": False}}}, timeout=10)


# -- final teardown: ensure demo mode ---------------------------------------
def test_final_demo_mode(auth):
    # Make sure ecobee live=false at the end
    requests.put(f"{BASE}/api/config", headers=auth,
                 json={"config": {"ecobee": {"live": False, "paired": False}}}, timeout=10)
    r = requests.get(f"{BASE}/api/state", headers=auth, timeout=10)
    ec = r.json()["config"]["ecobee"]
    assert ec["live"] is False
    assert ec["paired"] is False
