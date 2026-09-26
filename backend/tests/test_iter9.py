import os, time, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://c4-controller-clone.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(autouse=True, scope="module")
def cleanup():
    # Pre-clean
    requests.delete(f"{API}/clips", timeout=10)
    requests.put(f"{API}/voice/phrases", json={"phrases": {}}, timeout=10)
    requests.post(f"{API}/state/reset", timeout=10)
    yield
    requests.delete(f"{API}/clips", timeout=10)
    requests.put(f"{API}/voice/phrases", json={"phrases": {}}, timeout=10)
    requests.post(f"{API}/state/reset", timeout=10)


# ---------- Clips ----------
def test_clips_flow():
    r = requests.delete(f"{API}/clips"); assert r.status_code == 200
    r = requests.get(f"{API}/clips"); assert r.status_code == 200 and r.json() == []
    r1 = requests.post(f"{API}/camera/cam_garage/motion"); assert r1.status_code == 200
    time.sleep(0.05)
    r2 = requests.post(f"{API}/camera/cam_front/motion"); assert r2.status_code == 200
    clips = requests.get(f"{API}/clips").json()
    assert len(clips) == 2
    # newest first
    assert clips[0]["camera_id"] == "cam_front"
    assert clips[0]["camera_name"] == "Front Entry"
    assert clips[1]["camera_id"] == "cam_garage"
    assert clips[1]["camera_name"] == "Garage"
    for c in clips:
        for k in ("id", "camera_id", "camera_name", "ts"):
            assert k in c
    # delete
    requests.delete(f"{API}/clips")
    assert requests.get(f"{API}/clips").json() == []


def test_motion_invalid_camera():
    r = requests.post(f"{API}/camera/nonexistent/motion")
    assert r.status_code == 404


# ---------- Per-camera stream ----------
def test_camera_stream_demo_and_live():
    # demo first
    r = requests.get(f"{API}/camera/stream/cam_living")
    assert r.status_code == 200
    j = r.json()
    assert j.get("live") is False and j.get("demo") is True

    # set live + rtsp
    cfg = {"cameras": {"cam_living": {"live": True, "rtsp_url": "rtsp://127.0.0.1:1/x"}}}
    r = requests.put(f"{API}/config", json={"config": cfg})
    assert r.status_code == 200
    state = r.json()
    assert state["config"]["cameras"]["cam_living"]["live"] is True
    assert state["config"]["cameras"]["cam_living"]["rtsp_url"] == "rtsp://127.0.0.1:1/x"

    r = requests.get(f"{API}/camera/stream/cam_living")
    assert r.status_code == 200
    j = r.json()
    # ffmpeg may or may not be present - if not present, will return demo
    import shutil
    if shutil.which("ffmpeg"):
        assert j.get("live") is True
        assert j.get("hls_url") == "/api/camera/hls/cam_living/index.m3u8"
    else:
        assert j.get("live") is False

    # revert
    requests.put(f"{API}/config", json={"config": {"cameras": {"cam_living": {"live": False, "rtsp_url": ""}}}})


# ---------- Voice phrases ----------
def test_voice_phrases_persist():
    requests.put(f"{API}/voice/phrases", json={"phrases": {}})
    r = requests.get(f"{API}/voice/phrases")
    assert r.status_code == 200 and r.json() == {}
    r = requests.put(f"{API}/voice/phrases", json={"phrases": {"movie_night": "Movie time"}})
    assert r.status_code == 200
    r = requests.get(f"{API}/voice/phrases")
    assert r.json() == {"movie_night": "Movie time"}


def test_voice_scene_webhook():
    r = requests.get(f"{API}/voice/scene/movie_night")
    assert r.status_code == 200
    assert r.json().get("ok") is True
    r = requests.get(f"{API}/voice/scene/does_not_exist")
    assert r.status_code == 404


# ---------- Regression ----------
def test_state_and_pin():
    s = requests.get(f"{API}/state").json()
    assert "cameras" in s and len(s["cameras"]) >= 4
    assert "config" in s
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"})
    assert r.status_code == 200 and r.json().get("success") is True


def test_scenes_list_and_run():
    scenes = requests.get(f"{API}/scenes").json()
    ids = [s["id"] for s in scenes]
    for sid in ("all_off", "good_night", "movie_night", "whole_home_audio"):
        assert sid in ids
    r = requests.post(f"{API}/scene/movie_night")
    assert r.status_code == 200


def test_climate_and_away():
    r = requests.post(f"{API}/climate", json={"target_cool": 72})
    assert r.status_code == 200
    r = requests.post(f"{API}/away", json={"enabled": True})
    assert r.status_code == 200 and r.json()["away"] is True
    requests.post(f"{API}/away", json={"enabled": False})
