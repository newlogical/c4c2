"""Iteration 2 tests: camera stream, config, automations, triggers."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def reset(client):
    r = client.post(f"{API}/state/reset", timeout=15)
    assert r.status_code == 200
    # cleanup automations
    for a in client.get(f"{API}/automations", timeout=10).json():
        client.delete(f"{API}/automations/{a['id']}", timeout=10)


# --- Camera stream ---
def test_camera_stream_demo(client):
    r = client.get(f"{API}/camera/stream", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["live"] is False
    assert d["demo"] is True
    assert "hls_url" in d and d["hls_url"].startswith("http")


# --- Config ---
def test_config_update_and_persist(client):
    payload = {"config": {"matrix": {"live": True, "host": "10.0.0.5", "port": 23}}}
    r = client.put(f"{API}/config", json=payload, timeout=10)
    assert r.status_code == 200
    cfg = r.json()["config"]["matrix"]
    assert cfg["live"] is True and cfg["host"] == "10.0.0.5"
    # persist
    s = client.get(f"{API}/state", timeout=10).json()
    assert s["config"]["matrix"]["live"] is True
    # reset to demo
    client.put(f"{API}/config", json={"config": {"matrix": {"live": False}}}, timeout=10)


def test_config_test_demo_mode(client):
    # Ensure demo
    client.put(f"{API}/config", json={"config": {"matrix": {"live": False}}}, timeout=10)
    r = client.post(f"{API}/config/test/matrix", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False
    assert "demo" in d["detail"].lower()


def test_config_test_live_unreachable(client):
    client.put(f"{API}/config", json={"config": {"matrix": {"live": True, "host": "192.0.2.1", "port": 23}}}, timeout=10)
    r = client.post(f"{API}/config/test/matrix", timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False  # unreachable expected
    client.put(f"{API}/config", json={"config": {"matrix": {"live": False}}}, timeout=10)


# --- Automations CRUD ---
def test_automation_schedule_crud(client):
    payload = {
        "name": "TEST_Nightly",
        "enabled": True,
        "trigger": {"type": "schedule", "time": "22:30", "days": [0, 1, 2, 3, 4, 5, 6]},
        "action": {"scene_id": "good_night"},
    }
    r = client.post(f"{API}/automations", json=payload, timeout=10)
    assert r.status_code == 200
    a = r.json()
    aid = a["id"]
    assert a["name"] == "TEST_Nightly"

    # list
    lst = client.get(f"{API}/automations", timeout=10).json()
    assert any(x["id"] == aid for x in lst)

    # toggle disable
    payload["enabled"] = False
    r = client.put(f"{API}/automations/{aid}", json=payload, timeout=10)
    assert r.status_code == 200 and r.json()["enabled"] is False

    # run now → scene applied to state
    client.post(f"{API}/state/reset", timeout=10)
    r = client.post(f"{API}/automations/{aid}/run", timeout=10)
    assert r.status_code == 200
    assert r.json()["thermostat"]["target_cool"] == 68  # good_night effect

    # delete
    r = client.delete(f"{API}/automations/{aid}", timeout=10)
    assert r.status_code == 200
    lst = client.get(f"{API}/automations", timeout=10).json()
    assert not any(x["id"] == aid for x in lst)


def test_automation_run_404(client):
    r = client.post(f"{API}/automations/nonexistent/run", timeout=10)
    assert r.status_code == 404


def test_automation_update_404(client):
    payload = {
        "name": "x", "enabled": True,
        "trigger": {"type": "schedule", "time": "10:00", "days": [1]},
        "action": {"scene_id": "all_off"},
    }
    r = client.put(f"{API}/automations/nope", json=payload, timeout=10)
    assert r.status_code == 404


# --- Motion trigger ---
def test_trigger_motion_no_automation(client):
    client.post(f"{API}/state/reset", timeout=10)
    r = client.post(f"{API}/trigger/motion", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["event"] == "motion"
    assert d["fired"] == []
    assert d["state"]["camera"]["motion"] is True


def test_trigger_motion_fires_automation(client):
    payload = {
        "name": "TEST_MotionScene",
        "enabled": True,
        "trigger": {"type": "event", "event": "motion"},
        "action": {"scene_id": "movie_night"},
    }
    a = client.post(f"{API}/automations", json=payload, timeout=10).json()
    aid = a["id"]
    client.post(f"{API}/state/reset", timeout=10)
    r = client.post(f"{API}/trigger/motion", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "TEST_MotionScene" in d["fired"]
    tv = next(x for x in d["state"]["displays"] if x["id"] == "tv_living")
    assert tv["source"] == "atv1" and tv["power"] is True
    # cleanup
    client.delete(f"{API}/automations/{aid}", timeout=10)


# --- Driver command log status field ---
def test_command_log_has_status(client):
    client.post(f"{API}/state/reset", timeout=10)
    client.post(f"{API}/matrix/route", json={"display_id": "tv_office", "source_id": "atv1"}, timeout=10)
    s = client.get(f"{API}/state", timeout=10).json()
    assert len(s["command_log"]) > 0
    assert "status" in s["command_log"][0]
    # in demo mode → simulated
    assert s["command_log"][0]["status"] in ("simulated", "sent", "error")
