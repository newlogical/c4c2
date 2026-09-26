"""Iteration 3 tests: Samsung TV control (power, tvkey, config, test endpoint)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    # cleanup: revert tv config to demo
    s.put(f"{API}/config", json={"config": {"tv": {"live": False, "sets": {
        "tv_living": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_office": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_master": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_guest": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
    }}}}, timeout=10)


def test_state_has_tv_config(client):
    r = client.get(f"{API}/state", timeout=10)
    assert r.status_code == 200
    st = r.json()
    tv = st["config"]["tv"]
    assert "live" in tv
    assert "sets" in tv
    for did in ["tv_living", "tv_office", "tv_master", "tv_guest"]:
        assert did in tv["sets"]
        s = tv["sets"][did]
        for k in ["ip", "mac", "hdmi_input", "token"]:
            assert k in s


def test_display_power_logs_both_drivers(client):
    r = client.post(f"{API}/display/power", json={"display_id": "tv_living", "power": True}, timeout=10)
    assert r.status_code == 200
    st = r.json()
    d = next(x for x in st["displays"] if x["id"] == "tv_living")
    assert d["power"] is True
    log = st["command_log"]
    # top 2 entries should include SamsungTV and JTECH-MXT40
    drivers_top = {log[0]["driver"], log[1]["driver"]}
    assert "SamsungTV" in drivers_top
    assert "JTECH-MXT40" in drivers_top
    samsung_entry = next(e for e in log[:2] if e["driver"] == "SamsungTV")
    assert samsung_entry["status"] == "simulated"


def test_display_power_off_logs(client):
    r = client.post(f"{API}/display/power", json={"display_id": "tv_living", "power": False}, timeout=10)
    assert r.status_code == 200
    st = r.json()
    log = st["command_log"]
    assert any(e["driver"] == "SamsungTV" and "OFF" in e.get("note", "") for e in log[:5])


def test_tvkey_endpoint(client):
    for key in ["KEY_VOLUP", "KEY_VOLDOWN", "KEY_MUTE"]:
        r = client.post(f"{API}/display/tvkey", json={"source_id": "tv_office", "key": key}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert "command_log" in body
        top = body["command_log"][0]
        assert top["driver"] == "SamsungTV"
        assert key in top["command"]
        assert "Office TV" in top["note"]


def test_tvkey_unknown_display(client):
    r = client.post(f"{API}/display/tvkey", json={"source_id": "not_a_tv", "key": "KEY_VOLUP"}, timeout=10)
    assert r.status_code == 404


def test_config_put_tv_persists(client):
    payload = {"config": {"tv": {"live": True, "sets": {
        "tv_living": {"ip": "10.0.0.99", "mac": "AA:BB:CC:DD:EE:FF", "hdmi_input": 2, "token": "tok1"},
    }}}}
    r = client.put(f"{API}/config", json=payload, timeout=10)
    assert r.status_code == 200
    st = r.json()
    assert st["config"]["tv"]["live"] is True
    assert st["config"]["tv"]["sets"]["tv_living"]["ip"] == "10.0.0.99"
    # verify persistence via GET
    r2 = client.get(f"{API}/state", timeout=10)
    tv = r2.json()["config"]["tv"]
    assert tv["live"] is True
    assert tv["sets"]["tv_living"]["hdmi_input"] == 2
    # Note: PUT /api/config does shallow merge at device-level; nested 'sets' is replaced.
    # Frontend always sends full config so this is fine in practice.


def test_config_test_tv_live_unreachable(client):
    # tv.live is True from previous test with unreachable IP - should not 500
    r = client.post(f"{API}/config/test/tv", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "detail" in body


def test_config_test_tv_demo(client):
    # set tv back to demo
    client.put(f"{API}/config", json={"config": {"tv": {"live": False}}}, timeout=10)
    r = client.post(f"{API}/config/test/tv", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "demo" in body["detail"].lower()


def test_config_test_tv_live_no_ips(client):
    # live but clear all IPs
    client.put(f"{API}/config", json={"config": {"tv": {"live": True, "sets": {
        "tv_living": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_office": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_master": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
        "tv_guest": {"ip": "", "mac": "", "hdmi_input": 1, "token": ""},
    }}}}, timeout=10)
    r = client.post(f"{API}/config/test/tv", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "no tv ip" in body["detail"].lower() or "no ip" in body["detail"].lower()


def test_regression_matrix_route(client):
    r = client.post(f"{API}/matrix/route", json={"display_id": "tv_living", "source_id": "atv2"}, timeout=10)
    assert r.status_code == 200
    st = r.json()
    d = next(x for x in st["displays"] if x["id"] == "tv_living")
    assert d["source"] == "atv2"
