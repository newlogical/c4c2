"""Iteration 17 - First-Night Checklist endpoints + auth guard."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"})
    if r.status_code != 200:
        # try demo
        r = requests.post(f"{API}/auth/demo")
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# --- auth guard ---
def test_checklist_requires_auth():
    r = requests.get(f"{API}/checklist")
    assert r.status_code == 401


def test_checklist_tick_requires_auth():
    r = requests.post(f"{API}/checklist/ipad_wifi", json={"done": True})
    assert r.status_code == 401


# --- shape ---
def test_checklist_shape(auth):
    r = requests.get(f"{API}/checklist", headers=auth, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "done" in data and "total" in data
    assert data["total"] == 14
    assert len(data["items"]) == 14
    expected_ids = {"install", "ipad_wifi", "pin", "matrix_live", "matrix_wiring",
                    "tv_setup", "amp_live", "atv_paired", "ecobee_paired",
                    "cam_stream", "cam_apikey", "ptz_presets", "all_green", "remote_access"}
    got_ids = {i["id"] for i in data["items"]}
    assert got_ids == expected_ids
    for item in data["items"]:
        for k in ("id", "group", "title", "hint", "auto", "manual_allowed", "done", "target"):
            assert k in item, f"missing {k} in {item}"
    manual_items = {i["id"] for i in data["items"] if i["manual_allowed"]}
    assert manual_items == {"install", "ipad_wifi", "tv_setup", "ptz_presets", "remote_access"}


# --- manual tick ---
def test_manual_tick_ipad_wifi(auth):
    r = requests.post(f"{API}/checklist/ipad_wifi", json={"done": True}, headers=auth, timeout=10)
    assert r.status_code == 200
    data = r.json()
    item = next(i for i in data["items"] if i["id"] == "ipad_wifi")
    assert item["done"] is True
    # untick
    r = requests.post(f"{API}/checklist/ipad_wifi", json={"done": False}, headers=auth, timeout=10)
    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["id"] == "ipad_wifi")
    assert item["done"] is False


def test_tick_auto_item_rejected(auth):
    r = requests.post(f"{API}/checklist/pin", json={"done": True}, headers=auth, timeout=10)
    assert r.status_code == 400
    assert "automatically" in r.text.lower()


# --- pin change triggers auto done ---
def test_pin_change_marks_pin_done(auth):
    # Change PIN to 5678
    r = requests.post(f"{API}/auth/change-pin", json={"current": "1234", "new_pin": "5678"},
                     headers=auth, timeout=10)
    assert r.status_code == 200, r.text
    try:
        r = requests.get(f"{API}/checklist", headers=auth, timeout=10)
        assert r.status_code == 200
        item = next(i for i in r.json()["items"] if i["id"] == "pin")
        assert item["done"] is True
        assert item["auto"] is True
    finally:
        # restore to 1234
        r = requests.post(f"{API}/auth/change-pin", json={"current": "5678", "new_pin": "1234"},
                         headers=auth, timeout=10)
        assert r.status_code == 200, f"Failed to restore PIN: {r.text}"


# --- matrix map triggers matrix_wiring auto done ---
def test_matrix_map_marks_wiring_done(auth):
    r = requests.put(f"{API}/matrix/map",
                     json={"outputs": {"tv_living": 1, "tv_office": 2, "tv_master": 3, "tv_guest": 4},
                           "inputs": {"atv1": 1, "atv2": 2, "atv3": 3, "atv4": 4}},
                     headers=auth, timeout=10)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/checklist", headers=auth, timeout=15)
    assert r.status_code == 200
    item = next(i for i in r.json()["items"] if i["id"] == "matrix_wiring")
    assert item["done"] is True
    assert item["auto"] is True
