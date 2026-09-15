"""Backend API tests for Control4-style home controller."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://c4-controller-clone.preview.emergentagent.com").rstrip("/")
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


# --- root & state ---
def test_root(client):
    r = client.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json().get("demo_mode") is True


def test_get_state(client):
    r = client.get(f"{API}/state", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["pin"] == "1234"
    assert len(d["displays"]) == 4
    assert len(d["audio_zones"]) == 4
    assert len(d["sources"]) == 4
    assert len(d["scenes"]) == 4
    assert "_id" not in d


# --- auth ---
def test_pin_correct(client):
    r = client.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200 and r.json()["success"] is True


def test_pin_wrong(client):
    r = client.post(f"{API}/auth/pin", json={"pin": "0000"}, timeout=10)
    assert r.status_code == 200 and r.json()["success"] is False


# --- matrix ---
def test_matrix_route(client):
    r = client.post(f"{API}/matrix/route", json={"display_id": "tv_office", "source_id": "atv3"}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    tv = next(x for x in d["displays"] if x["id"] == "tv_office")
    assert tv["source"] == "atv3" and tv["power"] is True
    # persistence
    r2 = client.get(f"{API}/state", timeout=10).json()
    assert next(x for x in r2["displays"] if x["id"] == "tv_office")["source"] == "atv3"


def test_matrix_broadcast(client):
    r = client.post(f"{API}/matrix/broadcast", json={"source_id": "atv2"}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert all(x["source"] == "atv2" and x["power"] is True for x in d["displays"])


def test_matrix_route_404(client):
    r = client.post(f"{API}/matrix/route", json={"display_id": "nope", "source_id": "atv1"}, timeout=10)
    assert r.status_code == 404


# --- display ---
def test_display_power(client):
    r = client.post(f"{API}/display/power", json={"display_id": "tv_guest", "power": False}, timeout=10)
    assert r.status_code == 200
    tv = next(x for x in r.json()["displays"] if x["id"] == "tv_guest")
    assert tv["power"] is False


def test_display_remote(client):
    r = client.post(f"{API}/display/remote", json={"source_id": "atv1", "key": "up"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(r.json()["command_log"]) > 0


# --- audio ---
def test_audio_zone_multi(client):
    r = client.post(f"{API}/audio/zone", json={"zone_id": "audio_office", "source": "spotify", "volume": 55, "mute": False, "power": True}, timeout=10)
    assert r.status_code == 200
    z = next(x for x in r.json()["audio_zones"] if x["id"] == "audio_office")
    assert z["source"] == "spotify" and z["volume"] == 55 and z["power"] is True


def test_audio_group(client):
    r = client.post(f"{API}/audio/group", json={"source_id": "airplay", "volume": 40}, timeout=10)
    assert r.status_code == 200
    for z in r.json()["audio_zones"]:
        assert z["source"] == "airplay" and z["volume"] == 40 and z["power"] is True


# --- climate ---
def test_climate_all(client):
    r = client.post(f"{API}/climate", json={"mode": "heat", "fan": "on", "target_heat": 70, "target_cool": 76}, timeout=10)
    assert r.status_code == 200
    t = r.json()["thermostat"]
    assert t["mode"] == "heat" and t["fan"] == "on" and t["target_heat"] == 70 and t["target_cool"] == 76


def test_climate_clamp(client):
    r = client.post(f"{API}/climate", json={"target_heat": 999}, timeout=10)
    assert r.json()["thermostat"]["target_heat"] == 90


# --- camera ---
def test_camera_snapshot(client):
    r = client.post(f"{API}/camera/snapshot", json={}, timeout=10)
    assert r.status_code == 200 and r.json()["ok"] is True


# --- scenes ---
def test_scene_all_off(client):
    r = client.post(f"{API}/scene/all_off", timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert all(not x["power"] for x in d["displays"])
    assert all(z["mute"] and not z["power"] for z in d["audio_zones"])


def test_scene_movie_night(client):
    client.post(f"{API}/state/reset", timeout=10)
    r = client.post(f"{API}/scene/movie_night", timeout=10)
    d = r.json()
    tv = next(x for x in d["displays"] if x["id"] == "tv_living")
    az = next(x for x in d["audio_zones"] if x["id"] == "audio_living")
    assert tv["source"] == "atv1" and tv["power"] is True
    assert az["source"] == "atv1" and az["power"] is True


def test_scene_whole_home(client):
    r = client.post(f"{API}/scene/whole_home_audio", timeout=10)
    for z in r.json()["audio_zones"]:
        assert z["source"] == "spotify" and z["power"] is True


def test_scene_good_night(client):
    r = client.post(f"{API}/scene/good_night", timeout=10)
    d = r.json()
    assert d["thermostat"]["target_cool"] == 68
    assert all(z["mute"] for z in d["audio_zones"])


def test_scene_404(client):
    r = client.post(f"{API}/scene/nope", timeout=10)
    assert r.status_code == 404


def test_reset(client):
    r = client.post(f"{API}/state/reset", timeout=10)
    d = r.json()
    assert d["thermostat"]["target_cool"] == 74
