"""ARC enforcement: listen.ensure_arc against a fake Sony Bravia REST endpoint."""
import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import listen  # noqa: E402
import server  # noqa: E402

TV = {"output": "speaker", "accept_set": True, "calls": []}


class FakeBravia(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        TV["calls"].append((self.path, body["method"], body["version"], self.headers.get("X-Auth-PSK")))
        if body["method"] == "getSoundSettings":
            res = {"result": [[{"target": "outputTerminal", "currentValue": TV["output"]}]], "id": 1}
        elif body["method"] == "setSoundSettings":
            if TV["accept_set"]:
                TV["output"] = body["params"][0]["settings"][0]["value"]
            res = {"result": [], "id": 1}
        else:
            res = {"error": [12, "unknown"], "id": 1}
        out = json.dumps(res).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


@pytest.fixture(scope="module")
def fake_tv():
    srv = HTTPServer(("127.0.0.1", 0), FakeBravia)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"127.0.0.1:{srv.server_port}"
    srv.shutdown()


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def setup(fake_tv, monkeypatch):
    listen.D.update(db=server.db, state_key=server.STATE_KEY, log_limit=server.LOG_LIMIT)
    TV.update(output="speaker", accept_set=True, calls=[])

    async def fake_conn(tv_id):
        return {"ip": fake_tv, "psk": "test-psk", "live": True}, "Test TV"
    monkeypatch.setattr(listen, "_tv", fake_conn)
    monkeypatch.setattr(listen, "ARC_TRIES", 2)
    yield
    run(server.db.meta.update_one({"key": "arc_status"}, {"$unset": {"tv_test": ""}}))


async def _status():
    return (await server.db.meta.find_one({"key": "arc_status"}))["tv_test"]


def test_switches_speaker_to_audio_system():
    run(listen.ensure_arc("tv_test"))
    st = run(_status())
    assert st["ok"] and st["was"] == "speaker" and TV["output"] == "audioSystem"
    assert ("/sony/audio", "setSoundSettings", "1.1", "test-psk") in TV["calls"]


def test_already_on_arc_no_set():
    TV["output"] = "audioSystem"
    run(listen.ensure_arc("tv_test"))
    assert run(_status())["ok"]
    assert all(c[1] == "getSoundSettings" for c in TV["calls"])


def test_tv_refuses_records_warning(monkeypatch):
    TV["accept_set"] = False

    async def no_sleep(_s):
        return None
    monkeypatch.setattr(listen.asyncio, "sleep", no_sleep)
    run(listen.ensure_arc("tv_test"))
    st = run(_status())
    assert not st["ok"] and "speaker" in st["error"] and st["name"] == "Test TV"


def test_office_input_not_mapped():
    assert "5" not in listen.DEFAULT_ARC_INPUTS
    assert listen.DEFAULT_ARC_INPUTS == {"1": "tv_living", "2": "tv_master"}


def test_sound_check_fixes_arc_tvs_and_leaves_office():
    r = run(listen.tv_sound_check())
    by = {t["tv_id"]: t for t in r["tvs"]}
    assert {"tv_living", "tv_office", "tv_master"} <= set(by)
    assert by["tv_office"]["expects_arc"] is False and "fixed" not in by["tv_office"]
    assert by["tv_living"]["expects_arc"] and by["tv_living"]["ok"] and by["tv_living"]["output_label"] == "Audio System (ARC)"
    assert any(t.get("fixed") for t in r["tvs"])  # fake TV started on speakers
    assert ("/sony/audio", "setSoundSettings", "1.1", "test-psk") in TV["calls"]
    run(server.db.meta.update_one({"key": "arc_status"}, {"$unset": {"tv_living": "", "tv_master": ""}}))
