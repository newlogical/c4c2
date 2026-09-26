"""Iteration 8 backend tests: multi-camera, voice webhook, auto-discovery."""
import os
import time
import uuid
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # ensure clean state
    s.post(f"{BASE}/state/reset", timeout=15)
    yield s
    # cleanup
    s.post(f"{BASE}/state/reset", timeout=15)


# ---------- Multi-camera ----------
class TestMultiCamera:
    def test_state_has_cameras(self, client):
        r = client.get(f"{BASE}/state", timeout=10)
        assert r.status_code == 200
        cams = r.json().get("cameras", [])
        ids = [c["id"] for c in cams]
        for cid in ("cam_front", "cam_living", "cam_back", "cam_garage"):
            assert cid in ids, f"missing camera {cid}"
        names = {c["id"]: c["name"] for c in cams}
        assert names["cam_front"] == "Front Entry"
        assert names["cam_living"] == "Living Room"
        assert names["cam_back"] == "Backyard"
        assert names["cam_garage"] == "Garage"

    @pytest.mark.parametrize("cid", ["cam_front", "cam_living", "cam_back", "cam_garage"])
    def test_camera_stream_each(self, client, cid):
        r = client.get(f"{BASE}/camera/stream/{cid}", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["live"] is False
        assert d["demo"] is True
        assert isinstance(d.get("hls_url"), str) and d["hls_url"]

    def test_camera_motion_sets_flag_and_returns_state(self, client):
        r = client.post(f"{BASE}/camera/cam_living/motion", timeout=10)
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["camera"] == "cam_living"
        assert isinstance(body.get("fired"), list)
        cams = {c["id"]: c for c in body["state"]["cameras"]}
        assert cams["cam_living"]["motion"] is True

    def test_camera_motion_unknown_returns_404(self, client):
        r = client.post(f"{BASE}/camera/cam_bogus/motion", timeout=10)
        assert r.status_code == 404

    def test_camera_motion_fires_event_automation(self, client):
        # create a scene-triggering automation on motion
        auto = {
            "name": "TEST_iter8_motion_auto",
            "enabled": True,
            "trigger": {"type": "event", "event": "motion"},
            "action": {"scene_id": "all_off"},
        }
        cr = client.post(f"{BASE}/automations", json=auto, timeout=10)
        assert cr.status_code == 200
        auto_id = cr.json()["id"]
        try:
            r = client.post(f"{BASE}/camera/cam_back/motion", timeout=10)
            assert r.status_code == 200
            fired = r.json()["fired"]
            assert "TEST_iter8_motion_auto" in fired
        finally:
            client.delete(f"{BASE}/automations/{auto_id}", timeout=10)


# ---------- Voice webhook ----------
class TestVoiceWebhook:
    def test_voice_builtin_movie_night(self, client):
        r = client.get(f"{BASE}/voice/scene/movie_night", timeout=10)
        assert r.status_code == 200
        assert r.json() == {"ok": True, "scene": "movie_night"}
        # verify side effect (movie_night sets tv_living power True, source atv1)
        s = client.get(f"{BASE}/state", timeout=10).json()
        tv = next(d for d in s["displays"] if d["id"] == "tv_living")
        assert tv["power"] is True
        assert tv["source"] == "atv1"

    def test_voice_unknown_scene_404(self, client):
        r = client.get(f"{BASE}/voice/scene/does_not_exist_xyz", timeout=10)
        assert r.status_code == 404

    def test_voice_custom_scene(self, client):
        name = f"TEST_iter8_custom_{uuid.uuid4().hex[:6]}"
        cr = client.post(f"{BASE}/scenes", json={"name": name}, timeout=10)
        assert cr.status_code == 200
        sid = cr.json()["id"]
        try:
            r = client.get(f"{BASE}/voice/scene/{sid}", timeout=10)
            assert r.status_code == 200
            assert r.json()["ok"] is True
            assert r.json()["scene"] == sid
        finally:
            client.delete(f"{BASE}/scenes/{sid}", timeout=10)


# ---------- Auto-discovery ----------
class TestDiscover:
    def test_discover_demo(self, client):
        r = client.get(f"{BASE}/discover", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("demo") is True
        devs = d["devices"]
        assert devs["matrix"]["host"] == "192.168.1.20"
        assert devs["matrix"]["port"] == 23
        assert "host" in devs["amp"]
        assert devs["camera"]["rtsp_url"].startswith("rtsp://")
        for k in ("tv_living", "tv_office", "tv_master", "tv_guest"):
            assert k in devs["tv"]
            assert devs["tv"][k]["ip"]
            assert devs["tv"][k]["mac"]


# ---------- Regression sanity ----------
class TestRegression:
    def test_pin_correct(self, client):
        r = client.post(f"{BASE}/auth/pin", json={"pin": "1234"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_list_scenes_has_builtins(self, client):
        r = client.get(f"{BASE}/scenes", timeout=10)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        for bid in ("all_off", "good_night", "movie_night", "whole_home_audio"):
            assert bid in ids

    def test_away_toggle(self, client):
        r = client.post(f"{BASE}/away", json={"enabled": True}, timeout=10)
        assert r.status_code == 200
        assert r.json()["away"] is True
        r2 = client.post(f"{BASE}/away", json={"enabled": False}, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["away"] is False
