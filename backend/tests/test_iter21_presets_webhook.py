"""Iter 21 — Seeded presets (Yankees WFAN + Morning Market Brief), Morning automation,
Protect person webhook (404/token/arm gate/ignore non-person), test-person endpoint,
webhook-token rotation, /api/alerts auth gating."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/pin", json={"pin": "1234"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- Seeded presets ----------
class TestSeededPresets:
    def test_yankees_wfan_in_scenes(self, H):
        r = requests.get(f"{BASE}/api/scenes", headers=H, timeout=15)
        assert r.status_code == 200
        scenes = {s["id"]: s for s in r.json()}
        assert "preset_yankees_wfan" in scenes, "preset_yankees_wfan missing"
        p = scenes["preset_yankees_wfan"]
        assert p["name"] == "Yankees on WFAN"
        actions = p["actions"]
        # tunein_station wfan on stream_a
        t = [a for a in actions if a["type"] == "tunein_station"]
        assert len(t) == 1 and t[0]["target"] == "stream_a" and t[0]["value"] == "wfan"
        # amp_source airplay for all 4 zones
        srcs = {a["target"]: a["value"] for a in actions if a["type"] == "amp_source"}
        for z in ("audio_living", "audio_office", "audio_master", "audio_bathroom"):
            assert srcs.get(z) == "airplay", f"zone {z} not airplay"
        # amp_volume 40 for all 4 zones
        vols = {a["target"]: a["value"] for a in actions if a["type"] == "amp_volume"}
        for z in ("audio_living", "audio_office", "audio_master", "audio_bathroom"):
            assert vols.get(z) == 40, f"zone {z} volume != 40"

    def test_morning_brief_in_scenes(self, H):
        r = requests.get(f"{BASE}/api/scenes", headers=H, timeout=15)
        scenes = {s["id"]: s for s in r.json()}
        assert "preset_morning_brief" in scenes
        p = scenes["preset_morning_brief"]
        assert p["name"] == "Morning Market Brief"
        actions = p["actions"]
        t = [a for a in actions if a["type"] == "tunein_station"]
        assert len(t) == 1 and t[0]["target"] == "stream_b" and t[0]["value"] == "s165740"
        srcs = [a for a in actions if a["type"] == "amp_source"]
        assert any(a["target"] == "audio_office" and a["value"] == "airplay2" for a in srcs)
        vols = [a for a in actions if a["type"] == "amp_volume"]
        assert any(a["target"] == "audio_office" and a["value"] == 20 for a in vols)

    def test_yankees_pinned(self, H):
        r = requests.get(f"{BASE}/api/state", headers=H, timeout=15)
        assert r.status_code == 200
        st = r.json()
        assert "preset_yankees_wfan" in st.get("pinned_scenes", [])

    def test_morning_automation(self, H):
        r = requests.get(f"{BASE}/api/automations", headers=H, timeout=15)
        assert r.status_code == 200
        autos = {a["id"]: a for a in r.json()}
        assert "auto_morning_brief" in autos
        a = autos["auto_morning_brief"]
        assert a["enabled"] is True
        assert a["trigger"]["type"] == "schedule"
        assert a["trigger"]["time"] == "08:00"
        assert a["trigger"]["days"] == [1, 2, 3, 4, 5]
        assert a["action"]["scene_id"] == "preset_morning_brief"

    def test_run_yankees_logs(self, H):
        r = requests.post(f"{BASE}/api/scene/preset_yankees_wfan", headers=H, timeout=20)
        assert r.status_code == 200, r.text
        st = r.json()
        logs = st.get("command_log") or []
        # Combine recent log notes
        recent = " ".join([f"{(e.get('driver') or '')} {(e.get('command') or '')} {(e.get('note') or '')} {(e.get('transport') or '')}" for e in logs[:60]])
        # Linkplay WFAN
        assert "Linkplay" in recent or "linkplay" in recent.lower() or "WFAN" in recent or "TuneIn" in recent, f"No Linkplay/WFAN entry seen: {recent[:400]}"
        # WS66i amp source commands
        want_cmds = ["<11CH03", "<12CH03", "<13CH03", "<14CH03"]
        for w in want_cmds:
            assert w in recent, f"Missing WS66i command {w} in log"
        # Volume commands - look for 40
        assert "40" in recent


# ---------- Protect webhook / alerts ----------
class TestWebhook:
    def test_alerts_requires_auth(self):
        r = requests.get(f"{BASE}/api/alerts", timeout=15)
        assert r.status_code == 401

    def test_webhook_wrong_token_404_public(self):
        # Public — no auth header required
        r = requests.post(f"{BASE}/api/protect/webhook/definitely_wrong_xyz",
                          json={"alarm": {"triggers": [{"key": "person"}]}}, timeout=15)
        assert r.status_code == 404

    def test_webhook_disarmed_returns_alerted_false(self, H):
        # Ensure disarmed
        r = requests.post(f"{BASE}/api/security/arm", headers=H, json={"enabled": False}, timeout=15)
        assert r.status_code == 200
        # Get token from state
        st = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
        tok = (st.get("config") or {}).get("camera", {}).get("webhook_token")
        assert tok, "webhook_token missing in state"
        r = requests.post(f"{BASE}/api/protect/webhook/{tok}",
                          json={"alarm": {"triggers": [{"key": "person"}]}}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("alerted") is False

    def test_webhook_armed_person_alerted(self, H):
        requests.post(f"{BASE}/api/security/arm", headers=H, json={"enabled": True}, timeout=15)
        st = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
        tok = st["config"]["camera"]["webhook_token"]
        r = requests.post(f"{BASE}/api/protect/webhook/{tok}",
                          json={"alarm": {"triggers": [{"key": "person"}]}}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("alerted") is True
        # /api/alerts shows person_alert
        a = requests.get(f"{BASE}/api/alerts", headers=H, timeout=15).json()
        assert a.get("person_alert") is not None
        assert a["person_alert"].get("camera")

    def test_webhook_non_person_ignored(self, H):
        requests.post(f"{BASE}/api/security/arm", headers=H, json={"enabled": True}, timeout=15)
        st = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
        tok = st["config"]["camera"]["webhook_token"]
        r = requests.post(f"{BASE}/api/protect/webhook/{tok}",
                          json={"alarm": {"triggers": [{"key": "vehicle"}]}}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ignored") is True

    def test_test_person_endpoint(self, H):
        requests.post(f"{BASE}/api/security/arm", headers=H, json={"enabled": True}, timeout=15)
        r = requests.post(f"{BASE}/api/protect/test-person", headers=H, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j.get("alerted") is True
        assert j.get("armed") is True

    def test_test_person_requires_auth(self):
        r = requests.post(f"{BASE}/api/protect/test-person", timeout=15)
        assert r.status_code == 401

    def test_rotate_token(self, H):
        st = requests.get(f"{BASE}/api/state", headers=H, timeout=15).json()
        old = st["config"]["camera"]["webhook_token"]
        r = requests.post(f"{BASE}/api/protect/webhook-token", headers=H, timeout=15)
        assert r.status_code == 200
        new = r.json().get("token")
        assert new and new != old
        # Old token now 404
        r2 = requests.post(f"{BASE}/api/protect/webhook/{old}",
                           json={"alarm": {"triggers": [{"key": "person"}]}}, timeout=15)
        assert r2.status_code == 404
        # New token works (armed)
        r3 = requests.post(f"{BASE}/api/protect/webhook/{new}",
                           json={"alarm": {"triggers": [{"key": "person"}]}}, timeout=15)
        assert r3.status_code == 200

    def test_disarm_at_end(self, H):
        r = requests.post(f"{BASE}/api/security/arm", headers=H, json={"enabled": False}, timeout=15)
        assert r.status_code == 200
