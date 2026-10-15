"""Iter 22 — httpOnly cookie session auth, logout, CSRF origin guard, CORS credentials, device health."""
import os
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
OWN_ORIGIN = BASE


def _login():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/pin", json={"pin": "1234"}, timeout=15)
    return s, r


@pytest.fixture(scope="module")
def sess():
    s, r = _login()
    assert r.status_code == 200 and r.json().get("success") is True, r.text
    return s


# ---------- Login / cookie ----------
class TestPinCookie:
    def test_pin_sets_httponly_cookie_no_token(self):
        s, r = _login()
        assert r.status_code == 200
        body = r.json()
        assert body == {"success": True} or (body.get("success") is True and "token" not in body)
        assert "token" not in body
        sc = r.headers.get("set-cookie", "")
        assert "c4_session=" in sc
        low = sc.lower()
        assert "httponly" in low
        # backend emits SameSite=lax; the Emergent preview ingress rewrites to SameSite=None; Partitioned
        assert "samesite=lax" in low or "samesite=none" in low
        assert "secure" in low  # https public URL
        assert "path=/" in low
        assert s.cookies.get("c4_session")

    def test_state_with_cookie_200(self, sess):
        r = sess.get(f"{BASE}/api/state", timeout=15)
        assert r.status_code == 200
        assert "scenes" in r.json()

    def test_state_without_cookie_401(self):
        r = requests.get(f"{BASE}/api/state", timeout=15)
        assert r.status_code == 401

    def test_wrong_pin_no_cookie(self):
        r = requests.post(f"{BASE}/api/auth/pin", json={"pin": "0000"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("success") is False
        assert "c4_session" not in r.headers.get("set-cookie", "")
        # reset fail counter with good login
        _login()

    def test_demo_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{BASE}/api/auth/demo", timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("success") is True
        assert "token" not in r.json()
        assert s.cookies.get("c4_session")
        assert s.get(f"{BASE}/api/state", timeout=15).status_code == 200

    def test_bearer_header_still_works(self):
        s, _ = _login()
        tok = s.cookies.get("c4_session")
        r = requests.get(f"{BASE}/api/state", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 200

    def test_logout_invalidates(self):
        s, _ = _login()
        tok = s.cookies.get("c4_session")
        r = s.post(f"{BASE}/api/auth/logout", headers={"Origin": OWN_ORIGIN}, timeout=15)
        assert r.status_code == 200
        sc = r.headers.get("set-cookie", "")
        assert "c4_session=" in sc and ("max-age=0" in sc.lower() or "expires=" in sc.lower())
        assert s.get(f"{BASE}/api/state", timeout=15).status_code == 401
        # old token reused via cookie and bearer also rejected
        r2 = requests.get(f"{BASE}/api/state", cookies={"c4_session": tok}, timeout=15)
        assert r2.status_code == 401
        r3 = requests.get(f"{BASE}/api/state", headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r3.status_code == 401


# ---------- CSRF ----------
class TestCSRF:
    def test_evil_origin_403(self, sess):
        r = sess.post(f"{BASE}/api/scene/all_off", headers={"Origin": "https://evil.example.com"}, timeout=15)
        assert r.status_code == 403

    def test_own_origin_200(self, sess):
        r = sess.post(f"{BASE}/api/scene/all_off", headers={"Origin": OWN_ORIGIN}, timeout=15)
        assert r.status_code == 200, r.text

    def test_no_origin_200(self, sess):
        r = sess.post(f"{BASE}/api/scene/all_off", timeout=15)
        assert r.status_code == 200, r.text

    def test_lan_allowed_origin_200(self, sess):
        r = sess.post(f"{BASE}/api/scene/all_off", headers={"Origin": "http://192.168.0.10:3000"}, timeout=15)
        assert r.status_code == 200

    def test_unauth_evil_origin_401(self):
        r = requests.post(f"{BASE}/api/scene/all_off", headers={"Origin": "https://evil.example.com"}, timeout=15)
        assert r.status_code == 401


# ---------- CORS ----------
class TestCORS:
    def test_preflight_lan_origin(self):
        r = requests.options(f"{BASE}/api/state", headers={
            "Origin": "http://192.168.0.10:3000", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.headers.get("access-control-allow-origin") == "http://192.168.0.10:3000"
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_unknown_origin_not_echoed(self):
        r = requests.options(f"{BASE}/api/state", headers={
            "Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"}, timeout=15)
        assert r.headers.get("access-control-allow-origin") not in ("https://evil.example.com", "*")


# ---------- Regression ----------
class TestRegression:
    def test_scenes_automations_clips(self, sess):
        for p in ("/api/scenes", "/api/automations", "/api/clips", "/api/alerts"):
            r = sess.get(f"{BASE}{p}", timeout=15)
            assert r.status_code == 200, f"{p}: {r.status_code}"

    def test_preset_crud_order(self, sess):
        st = sess.get(f"{BASE}/api/scenes", timeout=15).json()
        yank = next(s for s in st if s["id"] == "preset_yankees_wfan")
        acts = yank["actions"][:3]
        r = sess.post(f"{BASE}/api/presets", json={"name": "TEST_cookie", "actions": acts}, timeout=15)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        rev = list(reversed(acts))
        r = sess.put(f"{BASE}/api/presets/{pid}", json={"name": "TEST_cookie2", "actions": rev}, timeout=15)
        assert r.status_code == 200
        got = next(s for s in sess.get(f"{BASE}/api/scenes", timeout=15).json() if s["id"] == pid)
        assert got["name"] == "TEST_cookie2"
        assert [(a["type"], a.get("target")) for a in got["actions"]] == [(a["type"], a.get("target")) for a in rev]
        assert sess.delete(f"{BASE}/api/scenes/{pid}", timeout=15).status_code == 200
        assert pid not in [s["id"] for s in sess.get(f"{BASE}/api/scenes", timeout=15).json()]

    def test_device_health(self, sess):
        r = sess.get(f"{BASE}/api/health/devices", timeout=40)
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == len(d["devices"]) and d["total"] > 0
        checks = {t["check"] for t in d["devices"]}
        print("checks:", checks, [(t.get("name") or t.get("id"), t["ip"], t["check"]) for t in d["devices"]])
        for t in d["devices"]:
            assert "online" in t and "latency_ms" in t
