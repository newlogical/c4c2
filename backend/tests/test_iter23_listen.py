# Iteration 23: room-based WS66i audio (Listen, Party Mode, Restore Defaults, Shortcuts, layout, LIVE confirmation)
import os
import subprocess
import time

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
FOUR = ["living", "office", "master", "bathroom"]


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


MDB = MongoClient(_env("/app/backend/.env", "MONGO_URL"))[_env("/app/backend/.env", "DB_NAME")]


@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    r = ss.post(f"{API}/auth/pin", json={"pin": "1234"})
    assert r.status_code == 200
    return ss


def rooms(s):
    return {r["id"]: r for r in s.get(f"{API}/listen").json()["rooms"]}


def reset(s):
    s.post(f"{API}/listen/party", json={"active": False})
    for rid, inp in zip(FOUR, [1, 5, 2, 6]):
        s.post(f"{API}/listen/room/{rid}", json={"power": True, "volume": 30, "mute": False})
    s.post(f"{API}/listen/restore-defaults")


# ---- auth / basics
def test_listen_requires_auth():
    assert requests.get(f"{API}/listen").status_code == 401
    assert requests.get(f"{API}/shortcuts").status_code == 401


def test_listen_structure(s):
    d = s.get(f"{API}/listen").json()
    assert "_id" not in d
    r = {x["id"]: x for x in d["rooms"]}
    vis = [x["id"] for x in d["rooms"] if x["visible"]]
    assert vis == FOUR
    assert not r["zone5"]["visible"] and not r["zone6"]["visible"]
    assert [x["input"] for x in r["living"]["sources"]] == [1, 3]
    assert [x["input"] for x in r["office"]["sources"]] == [5, 6]
    assert [x["input"] for x in r["master"]["sources"]] == [2, 4]
    assert [x["input"] for x in r["bathroom"]["sources"]] == [6, 1, 5, 2]
    assert r["bathroom"]["tv_id"] is None
    assert [x["input"] for x in d["party_sources"]] == [6, 1, 5, 2]
    assert [r[k]["default_input"] for k in FOUR] == [1, 5, 2, 6]


# ---- per-room controls
def test_room_controls_isolated(s):
    reset(s)
    before = rooms(s)
    s.post(f"{API}/listen/room/living", json={"power": False})
    r = s.post(f"{API}/listen/room/living", json={"input": 3})
    assert r.status_code == 200
    after = rooms(s)
    assert after["living"]["status"]["input"] == 3 and after["living"]["status"]["power"] is True
    for k in ["office", "master", "bathroom"]:
        assert after[k]["status"] == before[k]["status"]
    s.post(f"{API}/listen/room/office", json={"volume": 55, "mute": True})
    after = rooms(s)
    assert after["office"]["status"]["volume"] == 55 and after["office"]["status"]["mute"] is True
    assert after["living"]["status"]["volume"] == 30


def test_room_invalid_source_and_unknown(s):
    assert s.post(f"{API}/listen/room/living", json={"input": 5}).status_code == 400
    assert s.post(f"{API}/listen/room/nope", json={"power": True}).status_code == 404


def test_volume_clamped(s):
    s.post(f"{API}/listen/room/master", json={"volume": 150})
    assert rooms(s)["master"]["status"]["volume"] == 100
    s.post(f"{API}/listen/room/master", json={"volume": 30})


# ---- party
def test_party_flow(s):
    reset(s)
    s.post(f"{API}/listen/room/living", json={"input": 3, "volume": 40})
    s.post(f"{API}/listen/room/bathroom", json={"power": False})
    before = rooms(s)
    # make office non participant
    p = s.get(f"{API}/listen").json()["party"]
    for rid in FOUR:
        s.post(f"{API}/listen/party/room/{rid}", json={"join": rid != "office"})
    s.post(f"{API}/listen/party/source", json={"input": 6})
    r = s.post(f"{API}/listen/party", json={"active": True})
    assert r.status_code == 200 and r.json()["party"]["active"]
    a = rooms(s)
    for rid in ["living", "master", "bathroom"]:
        assert a[rid]["status"]["input"] == 6 and a[rid]["status"]["power"] and a[rid]["in_party"]
    assert a["office"]["status"] == before["office"]["status"] and not a["office"]["in_party"]
    # source change
    s.post(f"{API}/listen/party/source", json={"input": 5})
    a = rooms(s)
    assert all(a[x]["status"]["input"] == 5 for x in ["living", "master", "bathroom"])
    assert s.post(f"{API}/listen/party/source", json={"input": 3}).status_code == 400
    # 409 for source change on participant
    assert s.post(f"{API}/listen/room/living", json={"input": 1}).status_code == 409
    # master +5
    vols = {x: a[x]["status"]["volume"] for x in ["living", "master", "bathroom"]}
    s.post(f"{API}/listen/party/master", json={"delta": 5})
    a = rooms(s)
    for x, v in vols.items():
        assert a[x]["status"]["volume"] == min(100, v + 5)
    assert a["office"]["status"]["volume"] == before["office"]["status"]["volume"]
    # per-room volume
    s.post(f"{API}/listen/room/master", json={"volume": 22})
    assert rooms(s)["master"]["status"]["volume"] == 22
    # leave living -> restored
    s.post(f"{API}/listen/party/room/living", json={"join": False})
    a = rooms(s)
    assert a["living"]["status"] == before["living"]["status"] and not a["living"]["in_party"]
    # off -> restore everyone
    s.post(f"{API}/listen/party", json={"active": False})
    a = rooms(s)
    for rid in FOUR:
        assert a[rid]["status"] == before[rid]["status"], rid


def test_party_master_off_400(s):
    s.post(f"{API}/listen/party", json={"active": False})
    assert s.post(f"{API}/listen/party/master", json={"delta": 5}).status_code == 400


def test_restore_defaults(s):
    reset(s)
    s.post(f"{API}/listen/room/living", json={"input": 3, "volume": 44})
    s.post(f"{API}/listen/room/office", json={"power": False})
    for rid in FOUR:
        s.post(f"{API}/listen/party/room/{rid}", json={"join": rid in ("master", "bathroom")})
    s.post(f"{API}/listen/party", json={"active": True})
    r = s.post(f"{API}/listen/restore-defaults")
    assert r.status_code == 200
    d = r.json()
    assert d["party"]["active"] is False
    a = {x["id"]: x for x in d["rooms"]}
    assert [a[k]["status"]["input"] for k in FOUR] == [1, 5, 2, 6]
    assert a["living"]["status"]["volume"] == 44
    assert a["office"]["status"]["power"] is False


# ---- shortcuts
def _sc(s):
    return {x["name"]: x for x in s.get(f"{API}/shortcuts").json()}


def test_seeded_shortcuts(s):
    sc = _sc(s)
    for n in ["Watch TV", "Music Everywhere", "Bathroom TV Audio", "Good Night", "Restore Defaults"]:
        assert n in sc, n


def test_run_seeded_shortcuts(s):
    reset(s)
    sc = _sc(s)
    d = s.post(f"{API}/shortcuts/{sc['Music Everywhere']['id']}/run").json()
    assert d["party"]["active"] and sorted(d["party"]["rooms"]) == sorted(FOUR) and d["party"]["input"] == 6
    assert all(r["status"]["input"] == 6 and r["status"]["power"] for r in d["rooms"] if r["id"] in FOUR)
    d = s.post(f"{API}/shortcuts/{sc['Good Night']['id']}/run").json()
    assert d["party"]["active"] is False
    assert all(not r["status"]["power"] for r in d["rooms"] if r["id"] in FOUR)
    d = s.post(f"{API}/shortcuts/{sc['Watch TV']['id']}/run").json()
    a = {r["id"]: r for r in d["rooms"]}
    assert [a[k]["status"]["input"] for k in FOUR] == [1, 5, 2, 6]
    before = rooms(s)
    d = s.post(f"{API}/shortcuts/{sc['Bathroom TV Audio']['id']}/run").json()
    a = {r["id"]: r for r in d["rooms"]}
    assert a["bathroom"]["status"]["input"] == 1
    for k in ["living", "office", "master"]:
        assert a[k]["status"] == before[k]["status"]
    d = s.post(f"{API}/shortcuts/{sc['Restore Defaults']['id']}/run").json()
    assert {r["id"]: r for r in d["rooms"]}["bathroom"]["status"]["input"] == 6


def test_shortcut_crud(s):
    body = {"name": "TEST_sc", "icon": "Moon", "rooms": {"office": {"input": 6, "volume": 20}}, "favorite": False}
    c = s.post(f"{API}/shortcuts", json=body)
    assert c.status_code == 200
    sid = c.json()["id"]
    assert c.json()["rooms"] == {"office": {"input": 6, "volume": 20}}
    u = s.put(f"{API}/shortcuts/{sid}", json={**body, "name": "TEST_sc2"})
    assert u.json()["name"] == "TEST_sc2"
    assert _sc(s)["TEST_sc2"]["id"] == sid
    f = s.post(f"{API}/shortcuts/{sid}/favorite", json={"active": True})
    assert f.json()["favorite"] is True
    dup = s.post(f"{API}/shortcuts/{sid}/duplicate").json()
    assert dup["name"] == "TEST_sc2 (copy)" and dup["id"] != sid and dup["favorite"] is False
    ids = [x["id"] for x in s.get(f"{API}/shortcuts").json()]
    new = [ids[-1]] + ids[:-1]
    out = s.post(f"{API}/shortcuts/reorder", json={"ids": new}).json()
    assert [x["id"] for x in out] == new
    s.post(f"{API}/shortcuts/reorder", json={"ids": ids})
    r = s.post(f"{API}/shortcuts/{sid}/run")
    assert r.status_code == 200
    assert {x["id"]: x for x in r.json()["rooms"]}["office"]["status"]["input"] == 6
    for x in (sid, dup["id"]):
        assert s.delete(f"{API}/shortcuts/{x}").status_code == 200
    assert s.delete(f"{API}/shortcuts/{sid}").status_code == 404
    assert s.post(f"{API}/shortcuts", json={"name": ""}).status_code == 422


# ---- layout
def test_layout_invalid_default_and_label(s):
    d = s.get(f"{API}/listen").json()
    lay = {"rooms": [{k: r[k] for k in ("id", "name", "amp_zone", "visible", "default_input", "max_volume", "tv_id", "sources")} for r in d["rooms"]],
           "party_sources": d["party_sources"]}
    import copy
    bad = copy.deepcopy(lay)
    bad["rooms"][0]["default_input"] = 4
    assert s.put(f"{API}/listen/layout", json=bad).status_code == 400
    ok = copy.deepcopy(lay)
    ok["rooms"][0]["sources"][1]["label"] = "TEST Phone"
    r = s.put(f"{API}/listen/layout", json=ok)
    assert r.status_code == 200
    assert rooms(s)["living"]["sources"][1]["label"] == "TEST Phone"
    assert s.put(f"{API}/listen/layout", json=lay).status_code == 200
    assert rooms(s)["living"]["sources"][1]["label"] == "Mobile Device"


# ---- removed features
def test_health_and_checklist_no_old_devices(s):
    h = s.get(f"{API}/health/devices").json()
    txt = str(h).lower()
    for w in ["matrix", "apple", "camera", "nvr", "protect"]:
        assert w not in txt, w
    c = str(s.get(f"{API}/checklist").json()).lower()
    for w in ["matrix", "apple tv", "camera", "nvr"]:
        assert w not in c, w


def test_tv_key_does_not_touch_audio(s):
    before = rooms(s)
    st = s.get(f"{API}/state").json()
    for d in st["displays"]:
        r = s.post(f"{API}/display/tvkey", json={"source_id": d["id"], "key": "VolumeUp"})
        assert r.status_code == 200
        s.post(f"{API}/display/power", json={"display_id": d["id"], "power": True})
    after = rooms(s)
    for k in FOUR:
        assert after[k]["status"] == before[k]["status"]


# ---- LIVE mode with fake amp
def _set_live(live, host):
    MDB.system.update_one({"key": "main"}, {"$set": {"config.amp.live": live, "config.amp.host": host}})


@pytest.fixture
def fakeamp():
    procs = []

    def start(ignore):
        src = open("/tmp/fakeamp.py").read().replace("IGNORE_SOURCE = set()", f"IGNORE_SOURCE = {ignore!r}")
        open("/tmp/fakeamp_run.py", "w").write(src)
        p = subprocess.Popen(["python3", "/tmp/fakeamp_run.py"])
        procs.append(p)
        time.sleep(1)
        return p
    yield start
    for p in procs:
        p.kill()
        p.wait()
    _set_live(False, "192.168.0.43")


def test_live_confirmed_and_failures(s, fakeamp):
    s.post(f"{API}/listen/party", json={"active": False})
    p = fakeamp(set())
    _set_live(True, "127.0.0.1")
    r = s.post(f"{API}/listen/room/living", json={"power": True, "input": 3, "volume": 50})
    assert r.status_code == 200, r.text
    st = {x["id"]: x for x in r.json()["rooms"]}["living"]["status"]
    assert r.json()["live"] is True and st["input"] == 3 and abs(st["volume"] - 50) <= 2
    log = s.get(f"{API}/state").json()["command_log"][0]
    assert log["status"] == "confirmed"
    p.kill(); p.wait()
    fakeamp({13})
    r = s.post(f"{API}/listen/room/master", json={"power": True})
    r = s.post(f"{API}/listen/room/master", json={"input": 4})
    assert r.status_code == 424 and "did not confirm source" in r.json()["detail"]
    assert rooms(s)["master"]["status"]["input"] != 4
    _set_live(True, "127.0.0.2")
    r = s.post(f"{API}/listen/room/living", json={"volume": 10})
    assert r.status_code == 424 and "connect" in r.json()["detail"].lower()
