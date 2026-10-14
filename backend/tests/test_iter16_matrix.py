"""Iteration 16 — Matrix identify + wiring map (POST /matrix/identify, PUT /matrix/map)."""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    for line in Path('/app/frontend/.env').read_text().splitlines():
        if line.startswith('REACT_APP_BACKEND_URL='):
            BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
            break
API = f"{BASE_URL}/api"

DEFAULT_OUTPUTS = {"tv_living": 1, "tv_office": 2, "tv_master": 3, "tv_guest": 4}
DEFAULT_INPUTS = {"atv1": 1, "atv2": 2, "atv3": 3, "atv4": 4}


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---- auth gate ----
def test_matrix_identify_requires_auth():
    r = requests.post(f"{API}/matrix/identify", json={"input": 1, "output": 1}, timeout=10)
    assert r.status_code == 401


def test_matrix_map_requires_auth():
    r = requests.put(f"{API}/matrix/map", json={"outputs": {}, "inputs": {}}, timeout=10)
    assert r.status_code == 401


# ---- matrix/identify ----
def test_identify_simulated_and_logs(auth):
    r = requests.post(f"{API}/matrix/identify", headers=auth, json={"input": 2, "output": 3}, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["status"] == "simulated"
    # check log entry
    s = requests.get(f"{API}/state", headers=auth, timeout=10).json()
    log = s.get("command_log", [])
    assert any("#video_d out3 matrix=2" in (e.get("command") or e.get("cmd") or "") for e in log), \
        f"Expected command '#video_d out3 matrix=2' in log; got: {[(e.get('command') or e.get('cmd')) for e in log[-5:]]}"


def test_identify_input_out_of_range(auth):
    r = requests.post(f"{API}/matrix/identify", headers=auth, json={"input": 5, "output": 1}, timeout=10)
    assert r.status_code == 400


def test_identify_output_out_of_range(auth):
    r = requests.post(f"{API}/matrix/identify", headers=auth, json={"input": 1, "output": 0}, timeout=10)
    assert r.status_code == 400


# ---- matrix/map validation ----
def test_map_duplicate_outputs(auth):
    r = requests.put(f"{API}/matrix/map", headers=auth,
                     json={"outputs": {"tv_living": 2, "tv_office": 2}, "inputs": {}}, timeout=10)
    assert r.status_code == 400
    assert "once" in r.json().get("detail", "").lower()


def test_map_unknown_id(auth):
    r = requests.put(f"{API}/matrix/map", headers=auth,
                     json={"outputs": {"tv_bogus": 1}, "inputs": {}}, timeout=10)
    assert r.status_code == 400
    assert "unknown" in r.json().get("detail", "").lower()


def test_map_value_out_of_range(auth):
    r = requests.put(f"{API}/matrix/map", headers=auth,
                     json={"outputs": {"tv_living": 5}, "inputs": {}}, timeout=10)
    assert r.status_code == 400


def test_map_valid_swap_and_route_uses_new_numbers(auth):
    # Swap living<->office outputs, atv1<->atv2 inputs
    r = requests.put(f"{API}/matrix/map", headers=auth,
                     json={"outputs": {"tv_living": 2, "tv_office": 1},
                           "inputs": {"atv1": 2, "atv2": 1}}, timeout=10)
    assert r.status_code == 200, r.text
    s = r.json()
    displays = {d["id"]: d["output"] for d in s["displays"]}
    sources = {sr["id"]: sr["input"] for sr in s["sources"]}
    assert displays["tv_living"] == 2 and displays["tv_office"] == 1
    assert displays["tv_master"] == 3 and displays["tv_guest"] == 4
    assert sources["atv1"] == 2 and sources["atv2"] == 1

    # subsequent /display/route uses new numbers
    before_cmds = [(e.get("command") or e.get("cmd") or "") for e in requests.get(f"{API}/state", headers=auth, timeout=10).json().get("command_log", [])]
    r2 = requests.post(f"{API}/matrix/route", headers=auth,
                       json={"display_id": "tv_living", "source_id": "atv1"}, timeout=10)
    assert r2.status_code == 200, r2.text
    after_cmds = [(e.get("command") or e.get("cmd") or "") for e in requests.get(f"{API}/state", headers=auth, timeout=10).json().get("command_log", [])]
    assert any("out2 matrix=2" in c for c in after_cmds[:5]), \
        f"Expected out2 matrix=2; top entries: {after_cmds[:5]}"


def test_restore_defaults(auth):
    r = requests.put(f"{API}/matrix/map", headers=auth,
                     json={"outputs": DEFAULT_OUTPUTS, "inputs": DEFAULT_INPUTS}, timeout=10)
    assert r.status_code == 200, r.text
    s = r.json()
    displays = {d["id"]: d["output"] for d in s["displays"]}
    sources = {sr["id"]: sr["input"] for sr in s["sources"]}
    assert displays == DEFAULT_OUTPUTS
    assert sources == DEFAULT_INPUTS
