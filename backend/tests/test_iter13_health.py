"""Iteration 13: Device Health panel + docs cleanup regression tests."""
import os
import re
import time
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Backend testing uses frontend env for public URL
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    if not data.get("success"):
        # try demo bypass
        r2 = requests.post(f"{API}/auth/demo", timeout=10)
        assert r2.status_code == 200 and r2.json().get("success"), r2.text
        return r2.json()["token"]
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# --- Auth gate ------------------------------------------------------------
def test_health_devices_requires_auth():
    r = requests.get(f"{API}/health/devices", timeout=10)
    assert r.status_code == 401


# --- Core shape -----------------------------------------------------------
def test_health_devices_returns_all_mapped(auth_headers):
    t0 = time.time()
    r = requests.get(f"{API}/health/devices", headers=auth_headers, timeout=10)
    elapsed = time.time() - t0
    assert r.status_code == 200, r.text
    assert elapsed < 8, f"too slow: {elapsed:.2f}s"
    body = r.json()
    assert "checked_at" in body
    assert "devices" in body
    assert isinstance(body["online"], int)
    assert isinstance(body["total"], int)
    devices = body["devices"]
    by_id = {d["id"]: d for d in devices}
    expected_tvs = {
        "tv_living": "192.168.0.165",
        "tv_office": "192.168.0.177",
        "tv_master": "192.168.0.78",
        "tv_guest": "192.168.0.253",
    }
    for tid, ip in expected_tvs.items():
        assert tid in by_id, f"missing {tid}"
        assert by_id[tid]["ip"] == ip
        assert by_id[tid]["mac"], f"{tid} missing MAC"
        assert by_id[tid]["check"].startswith("TCP ")
        assert isinstance(by_id[tid]["online"], bool)
        assert "latency_ms" in by_id[tid]
        assert "live" in by_id[tid]

    assert "ecobee" in by_id
    assert by_id["ecobee"]["ip"] == "192.168.0.222"
    assert by_id["ecobee"]["check"] == "ping"

    assert "matrix" in by_id
    assert "amp" in by_id
    assert body["total"] >= 6


# --- RTSP camera handling -------------------------------------------------
def test_camera_rtsp_appears_in_health_without_leaking_creds(auth_headers):
    # set rtsp with embedded user:pass
    payload = {"config": {"cameras": {"cam_back": {"rtsp_url": "rtsp://user:pass@192.168.0.50:7447/abc"}}}}
    r = requests.put(f"{API}/config", headers=auth_headers, json=payload, timeout=10)
    assert r.status_code == 200, r.text
    try:
        h = requests.get(f"{API}/health/devices", headers=auth_headers, timeout=10).json()
        cam = next((d for d in h["devices"] if d["id"] == "cam_back"), None)
        assert cam is not None, "cam_back not in health list"
        assert cam["ip"] == "192.168.0.50"
        assert cam["port"] == 7447
        # ensure credentials not leaked
        assert "user" not in cam["ip"]
        assert "pass" not in cam["ip"]
    finally:
        # restore to empty
        r2 = requests.put(f"{API}/config", headers=auth_headers,
                          json={"config": {"cameras": {"cam_back": {"rtsp_url": ""}}}}, timeout=10)
        assert r2.status_code == 200


# --- Docs cleanup ---------------------------------------------------------
GUIDE = "/app/frontend/public/setup-guide.html"


def test_setup_guide_no_samsung_or_smartthings():
    with open(GUIDE) as f:
        txt = f.read()
    assert not re.search(r"samsung", txt, re.I), "Samsung mention still present"
    assert not re.search(r"smartthings", txt, re.I), "SmartThings mention still present"


def test_setup_guide_has_sony_section_and_ip_table():
    with open(GUIDE) as f:
        txt = f.read()
    assert 'id="part8"' in txt
    assert "Sony Bravia" in txt
    # Section 8.4 header
    assert re.search(r"8\.4\s+Sony Bravia", txt)
    for ip in ("192.168.0.165", "192.168.0.177", "192.168.0.78", "192.168.0.253"):
        assert ip in txt
    for sec in ("8.1", "8.2", "8.3", "8.4", "8.5", "8.6"):
        assert sec in txt, f"missing section {sec}"


# --- Regression: ensure devices left in DEMO at end -----------------------
def test_leave_devices_in_demo(auth_headers):
    s = requests.get(f"{API}/state", headers=auth_headers, timeout=10).json()
    c = s.get("config", {})
    for d in ("matrix", "amp", "ecobee", "tv", "camera", "appletv"):
        assert not (c.get(d) or {}).get("live"), f"{d} is LIVE but should be DEMO"
