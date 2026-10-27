"""Iter25: outside-access gaps via PUBLIC URL — password change/delete revoke sessions, validation edges, cookie flags,
remote user can manage accounts after PIN, remote logout, 404 on bad ids."""
import os
import time

import pyotp
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
PW = "correct-horse-battery"
TAG = int(time.time()) % 100000


def wait_new_step():
    time.sleep(31 - time.time() % 30)


@pytest.fixture(scope="module")
def lan():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/pin", json={"pin": "1234"})
    assert r.json()["success"]
    yield s


@pytest.fixture(scope="module")
def created(lan):
    ids = []
    yield ids
    for i in ids:
        lan.delete(f"{BASE}/remote/users/{i}")


def remote(ip):
    s = requests.Session()
    s.headers.update({"X-Smith-Remote": "1", "X-Forwarded-For": ip})
    return s


def make(lan, created, name):
    r = lan.post(f"{BASE}/remote/users", json={"username": name, "name": "T", "password": PW})
    assert r.status_code == 200, r.text
    created.append(r.json()["id"])
    return r.json()


def sign_in(s, name, pw=PW):
    e = s.post(f"{BASE}/remote/login", json={"username": name, "password": pw}).json()
    assert e["step"] == "enroll", e
    r = s.post(f"{BASE}/remote/login", json={"username": name, "password": pw, "code": pyotp.TOTP(e["secret"]).now()})
    assert r.json()["step"] == "done", r.text
    return e["secret"], r


# Validation edges
def test_validation_edges(lan, created):
    assert lan.post(f"{BASE}/remote/users", json={"username": "a" * 33, "password": PW}).status_code == 400
    assert lan.post(f"{BASE}/remote/users", json={"username": "bad name!", "password": PW}).status_code == 400
    assert lan.post(f"{BASE}/remote/users", json={"username": f"v{TAG}", "password": "x" * 11}).status_code == 400
    u = make(lan, created, f"V{TAG}x")  # stored lowercase
    assert u["username"] == f"v{TAG}x" and u["two_factor"] is False
    dup = lan.post(f"{BASE}/remote/users", json={"username": f"v{TAG}X", "password": PW})
    assert dup.status_code == 409
    assert lan.post(f"{BASE}/remote/users/{u['id']}/password", json={"password": "short"}).status_code == 400
    assert lan.post(f"{BASE}/remote/users/notanid/reset-2fa").status_code == 404
    assert lan.delete(f"{BASE}/remote/users/000000000000000000000000").status_code == 404


# Cookie flags, remote user manages accounts, password change revokes
def test_cookie_and_password_revoke(lan, created):
    name = f"p{TAG}"
    u = make(lan, created, name)
    s = remote("203.0.113.21")
    _, r = sign_in(s, name)
    sc = r.headers.get("set-cookie", "")
    assert "c4_session" in sc and "HttpOnly" in sc and "Secure" in sc, sc
    assert s.get(f"{BASE}/remote/users").status_code == 401  # needs PIN
    assert s.post(f"{BASE}/auth/pin", json={"pin": "1234"}).json()["success"]
    assert s.get(f"{BASE}/remote/users").status_code == 200  # everything allowed from outside after PIN
    assert s.get(f"{BASE}/state").status_code == 200
    assert lan.post(f"{BASE}/remote/users/{u['id']}/password", json={"password": "another-long-password"}).status_code == 200
    assert s.get(f"{BASE}/state").status_code == 401
    assert s.get(f"{BASE}/remote/me").json()["signed_in"] is False
    # old password no longer works, new one does (still confirmed -> step code)
    s2 = remote("203.0.113.22")
    assert s2.post(f"{BASE}/remote/login", json={"username": name, "password": PW}).status_code == 401
    assert s2.post(f"{BASE}/remote/login", json={"username": name, "password": "another-long-password"}).json() == {"step": "code"}


# Delete revokes, remote logout clears session
def test_delete_and_remote_logout(lan, created):
    name = f"d{TAG}"
    u = make(lan, created, name)
    s = remote("203.0.113.31")
    sign_in(s, name)
    assert s.post(f"{BASE}/auth/pin", json={"pin": "1234"}).json()["success"]
    assert s.post(f"{BASE}/remote/logout").status_code == 200
    assert s.get(f"{BASE}/remote/me").json()["signed_in"] is False
    # another sign-in (needs fresh step), then delete revokes
    secret = None
    wait_new_step()
    s3 = remote("203.0.113.32")
    assert s3.post(f"{BASE}/remote/login", json={"username": name, "password": PW}).json() == {"step": "code"}
    assert lan.delete(f"{BASE}/remote/users/{u['id']}").status_code == 200
    created.remove(u["id"])
    assert s3.post(f"{BASE}/remote/login", json={"username": name, "password": PW}).status_code == 401
    assert all(x["username"] != name for x in lan.get(f"{BASE}/remote/users").json())


# LAN session cookie is not accepted when the request is remote
def test_lan_session_not_valid_remote(lan):
    s = requests.Session()
    s.cookies.update(lan.cookies)
    s.headers.update({"X-Smith-Remote": "1"})
    assert s.get(f"{BASE}/state").status_code == 401
    assert s.get(f"{BASE}/remote/me").json()["signed_in"] is False
    assert lan.get(f"{BASE}/state").status_code == 200
