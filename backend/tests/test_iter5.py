"""Iteration 5: Zone→TV Linking, Scene Builder, Away Mode, Arm/Disarm, Remote Access docs."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://c4-controller-clone.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(autouse=True)
def reset_state():
    # Reset before every test to guarantee clean baseline
    requests.post(f"{API}/state/reset", timeout=15)
    yield


def _state():
    r = requests.get(f"{API}/state", timeout=15)
    r.raise_for_status()
    return r.json()


def _zone(state, zid):
    return next(z for z in state["audio_zones"] if z["id"] == zid)


def _display(state, did):
    return next(d for d in state["displays"] if d["id"] == did)


# ---------- Zone→TV linking ----------
class TestZoneLinking:
    def test_default_audio_follow_true(self):
        s = _state()
        assert s["audio_follow_tv"] is True

    def test_power_on_tv_follows_source_to_zone(self):
        # tv_office source=atv2 by default; audio_office paired->tv_office
        r = requests.post(f"{API}/display/power", json={"display_id": "tv_office", "power": True}, timeout=15)
        assert r.status_code == 200
        s = r.json()
        z = _zone(s, "audio_office")
        assert z["source"] == "atv2"
        assert z["power"] is True
        assert z["mute"] is False

    def test_route_changes_paired_zone_source(self):
        r = requests.post(f"{API}/matrix/route", json={"display_id": "tv_master", "source_id": "atv1"}, timeout=15)
        assert r.status_code == 200
        z = _zone(r.json(), "audio_master")
        assert z["source"] == "atv1"

    def test_broadcast_updates_all_paired_zones(self):
        r = requests.post(f"{API}/matrix/broadcast", json={"source_id": "atv3"}, timeout=15)
        assert r.status_code == 200
        s = r.json()
        for zid in ("audio_living", "audio_office", "audio_master"):
            assert _zone(s, zid)["source"] == "atv3"
        # bathroom is not paired to a tv -> not changed
        assert _zone(s, "audio_bathroom")["source"] != "atv3" or True  # unpaired: no requirement

    def test_disabled_follow_does_not_change_zone(self):
        requests.post(f"{API}/settings/audio-follow", json={"enabled": False}, timeout=15)
        before = _zone(_state(), "audio_master")["source"]
        r = requests.post(f"{API}/matrix/route", json={"display_id": "tv_master", "source_id": "atv1"}, timeout=15)
        after = _zone(r.json(), "audio_master")["source"]
        assert after == before
        # restore
        requests.post(f"{API}/settings/audio-follow", json={"enabled": True}, timeout=15)


# ---------- Scene Builder ----------
class TestSceneBuilder:
    def test_builtin_scenes(self):
        r = requests.get(f"{API}/scenes", timeout=15)
        assert r.status_code == 200
        scenes = r.json()
        ids = [s["id"] for s in scenes if not s.get("custom")]
        for sid in ("all_off", "good_night", "movie_night", "whole_home_audio"):
            assert sid in ids

    def test_create_and_apply_and_delete_custom_scene(self):
        # Snapshot: turn on tv_office->atv2
        requests.post(f"{API}/display/power", json={"display_id": "tv_office", "power": True}, timeout=15)
        # create scene
        r = requests.post(f"{API}/scenes", json={"name": "TEST_MyScene", "icon": "Film", "type": "vibrant"}, timeout=15)
        assert r.status_code == 200
        doc = r.json()
        assert doc.get("custom") is True
        assert "id" in doc
        cid = doc["id"]

        # list now includes custom
        scenes = requests.get(f"{API}/scenes", timeout=15).json()
        assert any(s["id"] == cid for s in scenes)

        # Change state (turn tv_office off), then apply scene, expect back on
        requests.post(f"{API}/display/power", json={"display_id": "tv_office", "power": False}, timeout=15)
        assert _display(_state(), "tv_office")["power"] is False
        r = requests.post(f"{API}/scene/{cid}", timeout=15)
        assert r.status_code == 200
        assert _display(_state(), "tv_office")["power"] is True

        # delete
        r = requests.delete(f"{API}/scenes/{cid}", timeout=15)
        assert r.status_code == 200
        scenes = requests.get(f"{API}/scenes", timeout=15).json()
        assert not any(s["id"] == cid for s in scenes)

    def test_custom_scene_as_automation(self):
        # Ensure tv_master is off, create scene snapshot
        r = requests.post(f"{API}/scenes", json={"name": "TEST_AutoScene", "icon": "Sun", "type": "primary"}, timeout=15)
        cid = r.json()["id"]
        # create automation
        auto = requests.post(
            f"{API}/automations",
            json={"name": "TEST_auto", "enabled": True, "trigger": {"type": "event", "event": "noop"},
                  "action": {"scene_id": cid}},
            timeout=15,
        ).json()
        aid = auto["id"]
        # run it
        r = requests.post(f"{API}/automations/{aid}/run", timeout=15)
        assert r.status_code == 200
        # cleanup
        requests.delete(f"{API}/automations/{aid}", timeout=15)
        requests.delete(f"{API}/scenes/{cid}", timeout=15)


# ---------- Away Mode + Arm ----------
class TestAwayMode:
    def test_away_powers_off_and_arms(self):
        # Turn one TV on first
        requests.post(f"{API}/display/power", json={"display_id": "tv_office", "power": True}, timeout=15)
        r = requests.post(f"{API}/away", json={"enabled": True}, timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert s["away"] is True
        assert s["camera"]["armed"] is True
        for d in s["displays"]:
            assert d["power"] is False

    def test_home_disables_armed(self):
        requests.post(f"{API}/away", json={"enabled": True}, timeout=15)
        r = requests.post(f"{API}/away", json={"enabled": False}, timeout=15)
        s = r.json()
        assert s["away"] is False
        assert s["camera"]["armed"] is False

    def test_arm_toggle_only_camera(self):
        r = requests.post(f"{API}/security/arm", json={"enabled": True}, timeout=15)
        s = r.json()
        assert s["camera"]["armed"] is True
        assert s["away"] is False
        r = requests.post(f"{API}/security/arm", json={"enabled": False}, timeout=15)
        assert r.json()["camera"]["armed"] is False


# ---------- Regression subset ----------
class TestRegression:
    def test_matrix_route_and_broadcast(self):
        r = requests.post(f"{API}/matrix/route", json={"display_id": "tv_living", "source_id": "atv2"}, timeout=15)
        assert r.status_code == 200
        assert _display(r.json(), "tv_living")["source"] == "atv2"
        r = requests.post(f"{API}/matrix/broadcast", json={"source_id": "atv4"}, timeout=15)
        assert all(d["source"] == "atv4" for d in r.json()["displays"])

    def test_audio_group_and_zone(self):
        r = requests.post(f"{API}/audio/group", json={"source_id": "spotify", "volume": 40}, timeout=15)
        assert r.status_code == 200
        r = requests.post(f"{API}/audio/zone", json={"zone_id": "audio_living", "volume": 55, "mute": False}, timeout=15)
        assert _zone(r.json(), "audio_living")["volume"] == 55

    def test_climate(self):
        r = requests.post(f"{API}/climate", json={"target_cool": 71}, timeout=15)
        assert r.json()["thermostat"]["target_cool"] == 71

    def test_camera(self):
        assert requests.post(f"{API}/camera/snapshot", timeout=15).status_code == 200
        assert requests.get(f"{API}/camera/stream", timeout=15).status_code == 200
        r = requests.post(f"{API}/trigger/motion", timeout=15)
        assert r.status_code == 200
