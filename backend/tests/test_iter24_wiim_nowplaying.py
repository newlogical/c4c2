# Iteration 24: WiiM now-playing (demo) status + play/pause, auth guard, command log
import os

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    r = ss.post(f"{API}/auth/pin", json={"pin": "1234"})
    assert r.status_code == 200
    yield ss
    # leave both playing=true
    for wid in ("wiim1", "wiim2"):
        if not ss.get(f"{API}/listen/wiim/{wid}/status").json().get("playing"):
            ss.post(f"{API}/listen/wiim/{wid}/play-pause")


# Status in demo mode
@pytest.mark.parametrize("wid,title,artist", [("wiim1", "Sunday Morning", "Maroon 5"),
                                              ("wiim2", "Here Comes the Sun", "The Beatles")])
def test_demo_status(s, wid, title, artist):
    r = s.get(f"{API}/listen/wiim/{wid}/status")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["title"] == title and d["artist"] == artist
    assert d["demo"] is True and isinstance(d["playing"], bool)
    assert d["mode"] == "wifi"


# Play/pause toggles and is logged
def test_play_pause_toggle_and_log(s):
    before = s.get(f"{API}/listen/wiim/wiim1/status").json()["playing"]
    r = s.post(f"{API}/listen/wiim/wiim1/play-pause")
    assert r.status_code == 200, r.text
    assert r.json()["playing"] is (not before)
    assert s.get(f"{API}/listen/wiim/wiim1/status").json()["playing"] is (not before)
    log = s.get(f"{API}/state").json()["command_log"]
    top = next(e for e in log[:10] if e.get("driver") == "WiiM")  # other suites may log concurrently
    assert top["driver"] == "WiiM" and top["status"] == "simulated"
    assert "play/pause" in top["note"]
    r2 = s.post(f"{API}/listen/wiim/wiim1/play-pause")
    assert r2.json()["playing"] is before


def test_wiim2_independent(s):
    a = s.get(f"{API}/listen/wiim/wiim1/status").json()["playing"]
    s.post(f"{API}/listen/wiim/wiim2/play-pause")
    assert s.get(f"{API}/listen/wiim/wiim1/status").json()["playing"] is a
    s.post(f"{API}/listen/wiim/wiim2/play-pause")


# Unknown id
def test_unknown_id(s):
    assert s.post(f"{API}/listen/wiim/nope/play-pause").status_code == 404
    assert s.get(f"{API}/listen/wiim/nope/status").status_code == 404


# Auth guard
def test_requires_auth():
    assert requests.get(f"{API}/listen/wiim/wiim1/status").status_code == 401
    assert requests.post(f"{API}/listen/wiim/wiim1/play-pause").status_code == 401
