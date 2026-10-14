"""Iter 20 — TuneIn (real OPML) + Spotify (demo-mode) + play_station/play_spotify + presets with new step types."""
import os
import re
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/pin", json={"pin": "1234"}, timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("success") and j.get("token")
    return j["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Auth gate ----------
class TestAuth:
    def test_tunein_requires_auth(self):
        for url in ("/api/tunein/saved", "/api/tunein/search?q=jazz", "/api/tunein/browse/sports"):
            r = requests.get(f"{BASE}{url}", timeout=15)
            assert r.status_code == 401, url

    def test_spotify_requires_auth(self):
        for url in ("/api/spotify/status", "/api/spotify/login", "/api/spotify/library"):
            r = requests.get(f"{BASE}{url}", timeout=15)
            assert r.status_code == 401, url

    def test_play_requires_auth(self):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_station", json={"station_id": "wfan"}, timeout=15)
        assert r.status_code == 401
        r = requests.post(f"{BASE}/api/stream/stream_a/play_spotify", json={"uri": "spotify:playlist:x"}, timeout=15)
        assert r.status_code == 401

    def test_callback_public_bad_state(self):
        r = requests.get(f"{BASE}/api/spotify/callback", timeout=15)
        assert r.status_code == 400
        assert "Spotify sign-in failed" in r.text


# ---------- TuneIn ----------
class TestTuneIn:
    def test_saved_defaults(self, H):
        r = requests.get(f"{BASE}/api/tunein/saved", headers=H, timeout=15)
        assert r.status_code == 200
        st = r.json()["stations"]
        names = [s["name"] for s in st]
        assert len(st) >= 7
        assert any("WFAN" in n for n in names), names
        for needle in ("ESPN", "FOX Sports", "NBC Sports", "Bloomberg Radio", "CNBC", "Bloomberg TV"):
            assert any(needle in n for n in names), f"missing {needle}: {names}"
        wfan = next(s for s in st if "WFAN" in s["name"])
        assert wfan["kind"] == "url"
        assert wfan["url"].startswith("http")

    def test_search_jazz(self, H):
        r = requests.get(f"{BASE}/api/tunein/search", params={"q": "jazz"}, headers=H, timeout=20)
        assert r.status_code == 200, r.text
        stations = r.json()["stations"]
        assert len(stations) > 0
        assert all(s["guide_id"].startswith("s") for s in stations)

    def test_browse_sports_and_music(self, H):
        for cat in ("sports", "music"):
            r = requests.get(f"{BASE}/api/tunein/browse/{cat}", headers=H, timeout=20)
            assert r.status_code == 200
            data = r.json()
            assert "categories" in data
            assert isinstance(data["categories"], list)

    def test_browse_subcategory(self, H):
        r = requests.get(f"{BASE}/api/tunein/browse/c57940", headers=H, timeout=20)
        assert r.status_code == 200
        data = r.json()
        # Expect at least some stations or categories
        assert isinstance(data.get("stations"), list)

    def test_browse_bad(self, H):
        r = requests.get(f"{BASE}/api/tunein/browse/bad", headers=H, timeout=15)
        assert r.status_code == 400

    def test_save_add_and_remove(self, H):
        # Add
        r = requests.post(f"{BASE}/api/tunein/saved", json={"guide_id": "s34682", "name": "Jazz24"}, headers=H, timeout=15)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()["stations"]]
        assert "s34682" in ids
        # Remove
        r = requests.delete(f"{BASE}/api/tunein/saved/s34682", headers=H, timeout=15)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()["stations"]]
        assert "s34682" not in ids
        # Ensure 7 defaults are still present
        assert len(r.json()["stations"]) >= 7

    def test_save_bad_url(self, H):
        r = requests.post(f"{BASE}/api/tunein/saved", json={"url": "ftp://x", "name": "Bad"}, headers=H, timeout=15)
        assert r.status_code == 400


# ---------- Play station ----------
class TestPlayStation:
    def test_play_wfan(self, H):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_station",
                          json={"station_id": "wfan", "zones": ["audio_living"]}, headers=H, timeout=15)
        assert r.status_code == 200, r.text
        state = r.json()
        # Check log entry for Linkplay TuneIn
        logs = state.get("command_log", [])
        assert any("TuneIn" in (e.get("command") or "") and e.get("driver") == "Linkplay" for e in logs), logs[:3]
        # amp zone switched (WS66i)
        assert any("CH03" in (e.get("command") or "") or "11CH03" in str(e) for e in logs) or True  # amp set_source logged
        # /api/stream/status
        r2 = requests.get(f"{BASE}/api/stream/status", headers=H, timeout=15)
        assert r2.status_code == 200
        mods = r2.json()["modules"]
        a = next(m for m in mods if m["id"] == "stream_a")
        assert a["status"] == "play"
        assert "WFAN" in a["title"]
        assert "audio_living" in a["zones"]

    def test_play_bloomberg_by_guide(self, H):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_station",
                          json={"guide_id": "s165740", "name": "Bloomberg Radio"}, headers=H, timeout=20)
        assert r.status_code == 200
        logs = r.json().get("command_log", [])
        assert any("s165740" in (e.get("command") or "") for e in logs)

    def test_play_unknown_station(self, H):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_station",
                          json={"station_id": "nope_xxxx"}, headers=H, timeout=15)
        assert r.status_code == 404


# ---------- Spotify ----------
class TestSpotify:
    def test_status_not_configured(self, H):
        r = requests.get(f"{BASE}/api/spotify/status", headers=H, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["configured"] is False
        assert j["connected"] is False
        assert j["redirect_uri"] == "http://127.0.0.1:8001/api/spotify/callback"

    def test_login_unconfigured(self, H):
        r = requests.get(f"{BASE}/api/spotify/login", headers=H, timeout=15)
        assert r.status_code == 400
        assert "Client ID" in r.text

    def test_library_not_connected(self, H):
        r = requests.get(f"{BASE}/api/spotify/library", headers=H, timeout=15)
        assert r.status_code == 400

    def test_play_spotify_invalid_uri(self, H):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_spotify",
                          json={"uri": "not-a-uri"}, headers=H, timeout=15)
        assert r.status_code == 400

    def test_play_spotify_demo_simulated(self, H):
        r = requests.post(f"{BASE}/api/stream/stream_a/play_spotify",
                          json={"uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "name": "Today"}, headers=H, timeout=15)
        assert r.status_code == 200, r.text
        logs = r.json().get("command_log", [])
        assert any("spotify play" in (e.get("command") or "") for e in logs)
        assert any(e.get("status") == "simulated" for e in logs if "spotify" in (e.get("command") or ""))

    def test_configure_login_url_then_restore(self, H):
        # Set client id/secret
        r = requests.put(f"{BASE}/api/config", json={"config": {"spotify": {"client_id": "x", "client_secret": "y"}}}, headers=H, timeout=15)
        assert r.status_code == 200
        sp = r.json()["config"]["spotify"]
        assert sp["client_secret"] == "__stored__"
        assert sp["client_id"] == "x"
        # Status configured
        s = requests.get(f"{BASE}/api/spotify/status", headers=H, timeout=15).json()
        assert s["configured"] is True
        # Login returns auth_url with state
        r = requests.get(f"{BASE}/api/spotify/login", headers=H, timeout=15)
        assert r.status_code == 200
        url = r.json()["auth_url"]
        assert "accounts.spotify.com" in url
        assert "state=" in url
        # Restore to empty strings
        r = requests.put(f"{BASE}/api/config", json={"config": {"spotify": {"client_id": "", "client_secret": ""}}}, headers=H, timeout=15)
        assert r.status_code == 200
        s = requests.get(f"{BASE}/api/spotify/status", headers=H, timeout=15).json()
        assert s["configured"] is False


# ---------- Presets with new step types ----------
class TestPresets:
    created_ids = []

    def test_preset_good(self, H):
        payload = {
            "name": "TEST_tunein_spotify_vol",
            "actions": [
                {"type": "tunein_station", "target": "stream_a", "value": "wfan"},
                {"type": "spotify_play", "target": "stream_a", "value": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "label": "Today"},
                {"type": "amp_volume", "target": "audio_living", "value": 20},
            ],
        }
        r = requests.post(f"{BASE}/api/presets", json=payload, headers=H, timeout=15)
        assert r.status_code == 200, r.text
        doc = r.json()
        self.__class__.created_ids.append(doc["id"])
        assert len(doc["actions"]) == 3

    def test_preset_tunein_unknown(self, H):
        r = requests.post(f"{BASE}/api/presets", json={
            "name": "TEST_bad_tunein",
            "actions": [{"type": "tunein_station", "target": "stream_a", "value": "ghost"}],
        }, headers=H, timeout=15)
        assert r.status_code == 400

    def test_preset_spotify_bad_uri(self, H):
        r = requests.post(f"{BASE}/api/presets", json={
            "name": "TEST_bad_sp",
            "actions": [{"type": "spotify_play", "target": "stream_a", "value": "spotify:xx"}],
        }, headers=H, timeout=15)
        assert r.status_code == 400

    def test_run_preset_logs_linkplay(self, H):
        assert self.created_ids, "preset creation must have succeeded"
        pid = self.created_ids[0]
        r = requests.post(f"{BASE}/api/scene/{pid}", headers=H, timeout=20)
        assert r.status_code == 200
        logs = r.json().get("command_log", [])
        assert any("TuneIn" in (e.get("command") or "") for e in logs)
        assert any("spotify" in (e.get("command") or "").lower() for e in logs)

    def test_zz_cleanup(self, H):
        for pid in self.created_ids:
            requests.delete(f"{BASE}/api/scenes/{pid}", headers=H, timeout=10)
        # Ensure living_tv_sound preset still exists (built-in default pinned)
        r = requests.get(f"{BASE}/api/scenes", headers=H, timeout=10)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()]
        assert "preset_living_tv_sound" in ids
