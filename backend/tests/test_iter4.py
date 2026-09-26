"""Iteration 4 backend tests: amp input mapping, SmartThings, TV volume, power-on retry."""
import os
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fall back: read frontend/.env
    from pathlib import Path
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module", autouse=True)
def _reset():
    requests.post(f"{API}/state/reset", timeout=10)
    yield
    # cleanup: revert live flags and reset
    requests.put(f"{API}/config", json={"config": {
        "smartthings": {"live": False, "token": "", "devices": {
            "tv_living": {"device_id": ""}, "tv_office": {"device_id": ""},
            "tv_master": {"device_id": ""}, "tv_guest": {"device_id": ""},
        }},
        "amp": {"live": False, "input_map": {
            "atv1": 1, "atv2": 2, "atv3": 3, "atv4": 4,
            "spotify": 5, "airplay": 6, "tv_audio": 6,
        }},
        "tv": {"live": False},
    }}, timeout=10)
    requests.post(f"{API}/state/reset", timeout=10)


def _state():
    return requests.get(f"{API}/state", timeout=10).json()


# --- Amp input mapping ---

def test_default_amp_input_map_present():
    s = _state()
    m = s["config"]["amp"]["input_map"]
    assert m == {"atv1": 1, "atv2": 2, "atv3": 3, "atv4": 4,
                 "spotify": 5, "airplay": 6, "tv_audio": 6}


def test_audio_zone_source_change_uses_mapped_input():
    # office zone = amp_zone 2 -> "<12..."; atv3 -> input 03
    r = requests.post(f"{API}/audio/zone", json={"zone_id": "audio_office", "source": "atv3"}, timeout=10)
    assert r.status_code == 200
    log0 = r.json()["command_log"][0]
    assert log0["command"] == "<12CH03", f"expected <12CH03 got {log0['command']}"


def test_audio_group_uses_mapped_input_for_airplay():
    r = requests.post(f"{API}/audio/group", json={"source_id": "airplay", "volume": 30}, timeout=10)
    assert r.status_code == 200
    logs = r.json()["command_log"]
    # the newest 8 entries are the audio_group ops (4 set_source + 4 set_volume interleaved)
    src_entries = [e for e in logs[:8] if "CH" in e.get("command", "")]
    assert len(src_entries) == 4
    for e in src_entries:
        assert e["command"].endswith("CH06"), f"expected CH06 got {e['command']}"


def test_apply_scene_whole_home_audio_uses_spotify_input_5():
    requests.post(f"{API}/state/reset", timeout=10)
    r = requests.post(f"{API}/scene/whole_home_audio", timeout=10)
    assert r.status_code == 200
    logs = r.json()["command_log"][:4]
    for e in logs:
        assert e["command"].endswith("CH05"), f"expected CH05 got {e['command']}"


def test_updating_input_map_changes_subsequent_command():
    # remap atv3 -> 4
    requests.put(f"{API}/config", json={"config": {"amp": {"input_map": {"atv3": 4}}}}, timeout=10)
    r = requests.post(f"{API}/audio/zone", json={"zone_id": "audio_office", "source": "atv3"}, timeout=10)
    log0 = r.json()["command_log"][0]
    assert log0["command"] == "<12CH04", f"expected <12CH04 got {log0['command']}"
    # restore
    requests.put(f"{API}/config", json={"config": {"amp": {"input_map": {"atv3": 3}}}}, timeout=10)


# --- SmartThings backend ---

def test_smartthings_default_config():
    s = _state()
    st = s["config"]["smartthings"]
    assert st["live"] is False
    assert "tv_living" in st["devices"]
    assert st["devices"]["tv_living"]["device_id"] == ""


def test_display_power_demo_no_smartthings_entry():
    requests.post(f"{API}/state/reset", timeout=10)
    r = requests.post(f"{API}/display/power", json={"display_id": "tv_office", "power": True}, timeout=10)
    assert r.status_code == 200
    logs = r.json()["command_log"]
    top_drivers = [e["driver"] for e in logs[:3]]
    assert "SmartThings" not in top_drivers
    assert "SamsungTV" in top_drivers
    assert "JTECH-MXT40" in top_drivers


def test_display_tvvolume_demo_logs_smartthings_simulated():
    r = requests.post(f"{API}/display/tvvolume", json={"display_id": "tv_living", "volume": 42}, timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["tv_volume"] == 42
    log0 = body["command_log"][0]
    assert log0["driver"] == "SmartThings"
    assert log0["status"] == "simulated"
    # verify persistence
    s = _state()
    living = next(d for d in s["displays"] if d["id"] == "tv_living")
    assert living["tv_volume"] == 42


def test_config_test_smartthings_demo_ok_false():
    r = requests.post(f"{API}/config/test/smartthings", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "detail" in body


# --- SmartThings live path ---

def test_smartthings_live_display_power_logs_setinput():
    requests.put(f"{API}/config", json={"config": {
        "smartthings": {"live": True, "token": "faketoken",
                        "devices": {"tv_living": {"device_id": "abc"}}},
    }}, timeout=10)
    r = requests.post(f"{API}/display/power", json={"display_id": "tv_living", "power": True}, timeout=10)
    assert r.status_code == 200
    logs = r.json()["command_log"][:5]
    st_entries = [e for e in logs if e["driver"] == "SmartThings" and "setInputSource" in e.get("command", "")]
    assert len(st_entries) >= 1, f"expected SmartThings setInputSource entry, got {logs}"
    # samsung tv entry should NOT include HDMI (select_input handed to ST)
    tv_entries = [e for e in logs if e["driver"] == "SamsungTV"]
    assert tv_entries
    assert "HDMI" not in tv_entries[0].get("note", ""), f"tv entry unexpectedly has HDMI: {tv_entries[0]}"
    # revert
    requests.put(f"{API}/config", json={"config": {
        "smartthings": {"live": False, "token": "",
                        "devices": {"tv_living": {"device_id": ""}}},
    }}, timeout=10)


# --- Power-on retry (demo, just no hang / 500) ---

def test_display_power_on_demo_returns_promptly():
    import time
    t = time.time()
    r = requests.post(f"{API}/display/power", json={"display_id": "tv_master", "power": True}, timeout=10)
    assert r.status_code == 200
    assert time.time() - t < 5
    tv_entries = [e for e in r.json()["command_log"] if e["driver"] == "SamsungTV"]
    assert tv_entries[0]["status"] == "simulated"


# --- Regression: matrix, audio zone volume/mute, climate, camera, automations ---

def test_regression_matrix_route():
    r = requests.post(f"{API}/matrix/route", json={"display_id": "tv_living", "source_id": "atv2"}, timeout=10)
    assert r.status_code == 200
    living = next(d for d in r.json()["displays"] if d["id"] == "tv_living")
    assert living["source"] == "atv2"


def test_regression_matrix_broadcast():
    r = requests.post(f"{API}/matrix/broadcast", json={"source_id": "atv1"}, timeout=10)
    assert r.status_code == 200
    for d in r.json()["displays"]:
        assert d["source"] == "atv1"


def test_regression_climate():
    r = requests.post(f"{API}/climate", json={"target_cool": 71}, timeout=10)
    assert r.status_code == 200
    assert r.json()["thermostat"]["target_cool"] == 71


def test_regression_camera_stream():
    r = requests.get(f"{API}/camera/stream", timeout=10)
    assert r.status_code == 200
    assert "hls_url" in r.json()


def test_regression_automation_crud_and_run():
    payload = {"name": "TEST_iter4", "enabled": True,
               "trigger": {"type": "event", "event": "motion"},
               "action": {"scene_id": "good_night"}}
    r = requests.post(f"{API}/automations", json=payload, timeout=10)
    assert r.status_code == 200
    aid = r.json()["id"]
    r = requests.post(f"{API}/automations/{aid}/run", timeout=10)
    assert r.status_code == 200
    r = requests.post(f"{API}/trigger/motion", timeout=10)
    assert r.status_code == 200
    assert "TEST_iter4" in r.json()["fired"]
    r = requests.delete(f"{API}/automations/{aid}", timeout=10)
    assert r.status_code == 200


def test_selfhost_artifacts_exist():
    from pathlib import Path
    assert Path("/app/SELF_HOST.md").exists()
    assert Path("/app/docker-compose.yml").exists()
    assert Path("/app/backend/Dockerfile").exists()
    assert Path("/app/frontend/Dockerfile").exists()
