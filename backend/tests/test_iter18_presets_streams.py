"""Iteration 18: presets CRUD, seeded Living-TV preset, streaming modules."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"
SEED_ID = "preset_living_tv_sound"


# ---- auth ----
@pytest.fixture(scope="session")
def token():
    # try PIN, fallback to demo
    r = requests.post(f"{API}/auth/pin", json={"pin": "1234"}, timeout=10)
    if r.ok and r.json().get("success"):
        return r.json()["token"]
    r = requests.post(f"{API}/auth/demo", timeout=10)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---- scenes list contains seeded preset ----
def test_scenes_contains_living_tv_preset(h):
    r = requests.get(f"{API}/scenes", headers=h, timeout=10)
    assert r.status_code == 200
    scenes = r.json()
    seeded = next((s for s in scenes if s["id"] == SEED_ID), None)
    assert seeded is not None, "seeded preset missing"
    assert seeded["name"] == "Watch TV in Living Room with Sound"
    assert isinstance(seeded.get("actions"), list) and len(seeded["actions"]) == 4
    types = [a["type"] for a in seeded["actions"]]
    assert types == ["tv_power", "tv_route", "tv_volume", "amp_source"]


# ---- run seed preset ----
def test_run_seed_preset_logs(h):
    r = requests.post(f"{API}/scene/{SEED_ID}", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    state = r.json()
    # living TV should be on, source atv1, tv_volume 0
    tv = next(d for d in state["displays"] if d["id"] == "tv_living")
    assert tv["power"] is True
    assert tv["source"] == "atv1"
    assert tv["tv_volume"] == 0
    # audio_living untouched volume
    az = next(z for z in state["audio_zones"] if z["id"] == "audio_living")
    assert az["source"] == "atv1"
    # look for WS66i <11CH01 in command_log
    log = state.get("command_log", [])
    cmds = " | ".join(e.get("command", "") for e in log)
    assert "<11CH01" in cmds or any("11CH01" in e.get("command", "") for e in log), f"missing WS66i command: {cmds[:300]}"
    # matrix route command for output 1 input 1
    assert any("1B01" in e.get("command", "") or "out1" in e.get("command", "").lower() or (e.get("driver") == "J-Tech Matrix" and "route" in e.get("note", "").lower()) for e in log)


# ---- Presets CRUD ----
@pytest.fixture
def temp_preset(h):
    body = {"name": "TEST_preset_tmp", "icon": "Sparkles",
            "actions": [{"type": "amp_volume", "target": "audio_office", "value": 20}]}
    r = requests.post(f"{API}/presets", headers=h, json=body, timeout=10)
    assert r.status_code == 200, r.text
    doc = r.json()
    yield doc
    requests.delete(f"{API}/scenes/{doc['id']}", headers=h, timeout=10)


def test_create_preset_ok(temp_preset):
    assert temp_preset["custom"] is True
    assert temp_preset["actions"][0]["value"] == 20
    assert temp_preset["id"]


def test_update_preset_ok(h, temp_preset):
    pid = temp_preset["id"]
    body = {"name": "TEST_preset_updated", "icon": "Sparkles",
            "actions": [{"type": "amp_volume", "target": "audio_office", "value": 55}]}
    r = requests.put(f"{API}/presets/{pid}", headers=h, json=body, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "TEST_preset_updated"
    assert r.json()["actions"][0]["value"] == 55


def test_update_non_preset_404(h):
    # built-in id is not a preset
    body = {"name": "x", "icon": "Sparkles",
            "actions": [{"type": "amp_volume", "target": "audio_office", "value": 10}]}
    r = requests.put(f"{API}/presets/all_off", headers=h, json=body, timeout=10)
    assert r.status_code == 404


def test_delete_scene(h):
    body = {"name": "TEST_preset_del", "icon": "Sparkles",
            "actions": [{"type": "amp_volume", "target": "audio_office", "value": 5}]}
    pid = requests.post(f"{API}/presets", headers=h, json=body, timeout=10).json()["id"]
    r = requests.delete(f"{API}/scenes/{pid}", headers=h, timeout=10)
    assert r.status_code == 200
    scenes = requests.get(f"{API}/scenes", headers=h, timeout=10).json()
    assert not any(s["id"] == pid for s in scenes)


# ---- Validation errors ----
@pytest.mark.parametrize("body,label", [
    ({"name": "T", "actions": [{"type": "weird", "target": "tv_living", "value": True}]}, "unknown-type"),
    ({"name": "T", "actions": [{"type": "tv_power", "target": "tv_zzz", "value": True}]}, "unknown-target"),
    ({"name": "T", "actions": [{"type": "amp_volume", "target": "audio_office", "value": 200}]}, "vol-200"),
    ({"name": "T", "actions": [{"type": "stream_preset", "target": "stream_a", "value": 13}]}, "fav-13"),
    ({"name": "T", "actions": []}, "empty"),
    ({"name": "   ", "actions": [{"type": "amp_volume", "target": "audio_office", "value": 10}]}, "blank-name"),
])
def test_preset_validation_400(h, body, label):
    body = {**body, "icon": "Sparkles"}
    r = requests.post(f"{API}/presets", headers=h, json=body, timeout=10)
    assert r.status_code == 400, f"[{label}] expected 400 got {r.status_code}: {r.text}"


# ---- Auth required ----
def test_presets_require_auth():
    r = requests.post(f"{API}/presets", json={"name": "x", "actions": []}, timeout=10)
    assert r.status_code == 401


# ---- Streaming ----
def test_stream_status(h):
    r = requests.get(f"{API}/stream/status", headers=h, timeout=10)
    assert r.status_code == 200
    mods = r.json()["modules"]
    assert len(mods) == 2
    by_id = {m["id"]: m for m in mods}
    assert by_id["stream_a"]["input"] == 3
    assert by_id["stream_a"]["source_name"] == "AirPlay 1"
    assert by_id["stream_b"]["input"] == 4
    assert by_id["stream_b"]["source_name"] == "AirPlay 2"
    for m in mods:
        assert "status" in m and "title" in m and "zones" in m


def test_stream_presets_6_demo(h):
    r = requests.get(f"{API}/stream/stream_a/presets", headers=h, timeout=10)
    assert r.status_code == 200
    presets = r.json()["presets"]
    assert len(presets) == 6
    assert presets[1]["name"] == "Discover Weekly"


def test_stream_play_preset_and_zones(h):
    body = {"preset": 2, "zones": ["audio_office", "audio_bathroom"]}
    r = requests.post(f"{API}/stream/stream_b/play", headers=h, json=body, timeout=15)
    assert r.status_code == 200, r.text
    state = r.json()
    log = state["command_log"]
    cmds = [e.get("command", "") for e in log]
    assert any("MCUKeyShortClick:2" in c for c in cmds), cmds[:10]
    # <12CH04 (zone 2 -> input 4) and <14CH04 (zone 4 -> input 4)
    assert any("12CH04" in c for c in cmds), f"missing 12CH04: {cmds[:10]}"
    assert any("14CH04" in c for c in cmds), f"missing 14CH04: {cmds[:10]}"
    # status check
    s = requests.get(f"{API}/stream/status", headers=h, timeout=10).json()
    sb = next(m for m in s["modules"] if m["id"] == "stream_b")
    assert sb["status"] == "play"
    assert sb["title"] == "Discover Weekly"
    assert set(sb["zones"]) >= {"audio_office", "audio_bathroom"}


def test_stream_cmd_play_pause_toggles(h):
    # ensure playing first
    requests.post(f"{API}/stream/stream_b/play", headers=h,
                  json={"preset": 1, "zones": []}, timeout=10)
    s0 = next(m for m in requests.get(f"{API}/stream/status", headers=h).json()["modules"] if m["id"] == "stream_b")
    r = requests.post(f"{API}/stream/stream_b/cmd", headers=h, json={"cmd": "play_pause"}, timeout=10)
    assert r.status_code == 200
    s1 = next(m for m in requests.get(f"{API}/stream/status", headers=h).json()["modules"] if m["id"] == "stream_b")
    assert s0["status"] != s1["status"]


def test_stream_bad_cmd_400(h):
    r = requests.post(f"{API}/stream/stream_a/cmd", headers=h, json={"cmd": "nope"}, timeout=10)
    assert r.status_code == 400


def test_stream_unknown_module_404(h):
    r = requests.get(f"{API}/stream/stream_zzz/presets", headers=h, timeout=10)
    assert r.status_code == 404


def test_stream_unknown_zone_400(h):
    r = requests.post(f"{API}/stream/stream_a/play", headers=h,
                     json={"preset": 1, "zones": ["bogus_zone"]}, timeout=10)
    assert r.status_code == 400


# ---- Preset mixing stream_preset + amp_source runs ----
def test_preset_mixed_stream_and_amp(h):
    body = {"name": "TEST_mixed", "icon": "Sparkles", "actions": [
        {"type": "stream_preset", "target": "stream_a", "value": 3},
        {"type": "amp_source", "target": "audio_master", "value": "airplay"},
    ]}
    r = requests.post(f"{API}/presets", headers=h, json=body, timeout=10)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    try:
        rr = requests.post(f"{API}/scene/{pid}", headers=h, timeout=15)
        assert rr.status_code == 200, rr.text
        log = rr.json()["command_log"]
        cmds = [e.get("command", "") for e in log]
        assert any("MCUKeyShortClick:3" in c for c in cmds)
        az = next(z for z in rr.json()["audio_zones"] if z["id"] == "audio_master")
        assert az["source"] == "airplay"
    finally:
        requests.delete(f"{API}/scenes/{pid}", headers=h, timeout=10)
