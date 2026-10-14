"""Iteration 14 — single camera (UniFi G6 PTZ) + NVR Device-health coverage."""
import os
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/') if os.environ.get('REACT_APP_BACKEND_URL') else None
if not BASE_URL:
    # fallback to frontend/.env
    from pathlib import Path
    for line in Path('/app/frontend/.env').read_text().splitlines():
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
            break

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    return data["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- state shape ---
def test_state_single_camera(auth):
    r = requests.get(f"{API}/state", headers=auth, timeout=10)
    assert r.status_code == 200
    s = r.json()
    cams = s.get("cameras", [])
    ids = [c["id"] for c in cams]
    assert ids == ["cam_front"], f"expected only cam_front, got {ids}"
    assert cams[0]["name"] == "Front Entry"
    cfg = s["config"]
    assert cfg["camera"]["ip"] == "192.168.0.73"
    assert cfg["camera"]["mac"] == "8C:ED:E1:DA:15:4F"
    assert cfg["camera"]["model"] == "UniFi G6 PTZ"
    assert cfg["nvr"]["ip"] == "192.168.0.166"
    assert cfg["nvr"]["mac"] == "74:FA:29:4B:01:30"
    # No demo cameras in cfg.cameras
    assert all(cid not in (cfg.get("cameras") or {}) for cid in ("cam_living", "cam_back", "cam_garage"))


# --- rtsp mask & unmask ---
def test_rtsp_masked_and_persisted(auth):
    real = "rtsps://192.168.0.166:7441/abc?enableSrtp"
    r = requests.put(f"{API}/config", headers=auth,
                     json={"config": {"camera": {"rtsp_url": real}}}, timeout=10)
    assert r.status_code == 200
    s = r.json()
    assert s["config"]["camera"]["rtsp_url"] == "__stored__"

    # Resend mask -> stored value preserved
    r2 = requests.put(f"{API}/config", headers=auth,
                      json={"config": {"camera": {"rtsp_url": "__stored__"}}}, timeout=10)
    assert r2.status_code == 200
    # verify via /camera/stream/cam_front - should not error (live still false -> demo mode)
    rs = requests.get(f"{API}/camera/stream/cam_front", timeout=10)
    assert rs.status_code == 200
    # Teardown: reset rtsp_url to ''
    r3 = requests.put(f"{API}/config", headers=auth,
                      json={"config": {"camera": {"rtsp_url": ""}}}, timeout=10)
    assert r3.status_code == 200


# --- device health ---
def test_health_includes_nvr_and_cam(auth):
    r = requests.get(f"{API}/health/devices", headers=auth, timeout=30)
    assert r.status_code == 200
    data = r.json()
    devs = {d["id"]: d for d in data["devices"]}
    assert "nvr" in devs, f"nvr missing. ids={list(devs.keys())}"
    assert devs["nvr"]["ip"] == "192.168.0.166"
    assert devs["nvr"]["check"] == "TCP 7441"
    assert "cam_front" in devs
    assert devs["cam_front"]["ip"] == "192.168.0.73"
    assert devs["cam_front"]["check"] == "ping"
    # Expected total 15: 4 TVs + 4 ATVs + ecobee + matrix + amp + 2 streamers + nvr + cam_front = 15
    assert data["total"] == 15, f"expected 15 health targets, got {data['total']} :: {list(devs.keys())}"


# --- test_connection with camera live=true + rtsps unreachable in cloud ---
def test_camera_test_connection_unreachable(auth):
    # set camera live true with a RTSPS URL
    requests.put(f"{API}/config", headers=auth,
                 json={"config": {"camera": {"live": True, "rtsp_url": "rtsps://192.168.0.166:7441/abc?enableSrtp"}}}, timeout=10)
    r = requests.post(f"{API}/config/test/camera", headers=auth, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert isinstance(body.get("detail"), str) and body["detail"], "expected an error detail"
    # Teardown — restore live=false, clear url
    requests.put(f"{API}/config", headers=auth,
                 json={"config": {"camera": {"live": False, "rtsp_url": ""}}}, timeout=10)
