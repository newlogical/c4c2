"""Outside access: remote requests (via the local HTTPS gateway) need username + password + TOTP, then the PIN."""
import time

import pyotp
import pytest
import requests

LAN = "http://127.0.0.1:8001/api"
REMOTE_H = {"X-Smith-Remote": "1", "X-Forwarded-For": "203.0.113.7"}
USER = f"client{int(time.time()) % 100000}"
PW = "correct-horse-battery"


@pytest.fixture(scope="module")
def lan():
    s = requests.Session()
    assert s.post(f"{LAN}/auth/pin", json={"pin": "1234"}).json()["success"]
    yield s


@pytest.fixture(scope="module")
def user(lan):
    r = lan.post(f"{LAN}/remote/users", json={"username": USER, "name": "Client", "password": PW})
    assert r.status_code == 200, r.text
    u = r.json()
    yield u
    lan.delete(f"{LAN}/remote/users/{u['id']}")


def remote():
    s = requests.Session()
    s.headers.update(REMOTE_H)
    return s


def wait_new_step():
    time.sleep(31 - time.time() % 30)


def test_lan_unchanged_and_remote_blocked():
    assert requests.get(f"{LAN}/bootstrap").json()["remote"] is False
    r = remote()
    b = r.get(f"{LAN}/bootstrap").json()
    assert b["remote"] is True and b["demo_mode"] is False
    assert r.get(f"{LAN}/state").status_code == 401
    assert r.get(f"{LAN}/camera/hls/cam_front/index.m3u8").status_code == 401
    assert r.post(f"{LAN}/auth/demo").status_code == 404
    assert r.post(f"{LAN}/protect/webhook/x").status_code == 404
    assert r.post(f"{LAN}/auth/pin", json={"pin": "1234"}).status_code == 401  # PIN alone is not enough outside


def test_validation(lan):
    assert lan.post(f"{LAN}/remote/users", json={"username": "ab", "password": PW}).status_code == 400
    assert lan.post(f"{LAN}/remote/users", json={"username": "shortpw", "password": "short"}).status_code == 400
    assert requests.post(f"{LAN}/remote/users", json={"username": "noauth", "password": PW}).status_code == 401
    assert requests.post(f"{LAN}/remote/login", json={"username": "x", "password": "y"}).status_code == 400


def test_full_remote_flow(lan, user):
    r = remote()
    assert r.post(f"{LAN}/remote/login", json={"username": USER, "password": "wrong-password-x"}).status_code == 401
    e = r.post(f"{LAN}/remote/login", json={"username": USER.upper(), "password": PW}).json()
    assert e["step"] == "enroll" and e["otpauth_uri"].startswith("otpauth://totp/")
    totp = pyotp.TOTP(e["secret"])
    assert r.post(f"{LAN}/remote/login", json={"username": USER, "password": PW, "code": "000000"}).status_code == 401
    done = r.post(f"{LAN}/remote/login", json={"username": USER, "password": PW, "code": totp.now()})
    assert done.json()["step"] == "done"
    assert r.get(f"{LAN}/remote/me").json() == {"remote": True, "signed_in": True, "username": USER}
    assert r.get(f"{LAN}/state").status_code == 401  # still needs the PIN
    assert r.post(f"{LAN}/auth/pin", json={"pin": "1234"}).json()["success"]
    assert r.get(f"{LAN}/state").status_code == 200
    # Lock keeps the sign-in, asks for the PIN again
    r.post(f"{LAN}/auth/logout")
    assert r.get(f"{LAN}/state").status_code == 401
    assert r.get(f"{LAN}/remote/me").json()["signed_in"] is True
    # The same code can't be replayed; a second device needs the code
    r2 = remote()
    assert r2.post(f"{LAN}/remote/login", json={"username": USER, "password": PW}).json() == {"step": "code"}
    assert r2.post(f"{LAN}/remote/login", json={"username": USER, "password": PW, "code": totp.now()}).status_code == 401
    wait_new_step()
    assert r2.post(f"{LAN}/remote/login", json={"username": USER, "password": PW, "code": totp.now()}).json()["step"] == "done"
    # Admin view + revoking access
    listed = next(u for u in lan.get(f"{LAN}/remote/users").json() if u["username"] == USER)
    assert listed["two_factor"] is True and "password_hash" not in listed and listed["last_login_ip"] == "203.0.113.7"
    assert lan.post(f"{LAN}/remote/users/{user['id']}/reset-2fa").status_code == 200
    assert r.get(f"{LAN}/remote/me").json()["signed_in"] is False
    assert r2.get(f"{LAN}/remote/me").json()["signed_in"] is False


def test_lockout(lan):
    name = f"lock{int(time.time()) % 100000}"
    u = lan.post(f"{LAN}/remote/users", json={"username": name, "password": PW}).json()
    s = requests.Session()
    s.headers.update({"X-Smith-Remote": "1", "X-Forwarded-For": "198.51.100.9"})
    codes = [s.post(f"{LAN}/remote/login", json={"username": name, "password": "nope-nope-nope"}).status_code for _ in range(5)]
    assert codes == [401] * 5
    assert s.post(f"{LAN}/remote/login", json={"username": name, "password": PW}).status_code == 429
    lan.delete(f"{LAN}/remote/users/{u['id']}")
