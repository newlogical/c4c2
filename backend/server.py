from fastapi import FastAPI, APIRouter, HTTPException, Request, Response
from urllib.parse import urlparse
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import sys
import ipaddress
import logging
import copy
import uuid
import shutil
import subprocess
import asyncio
import socket
import urllib.request
import secrets
import re
import bcrypt
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

import drivers
import homekit
import protect
import linkplay
import music
import listen
import secrets as _secrets
from fastapi.responses import HTMLResponse

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Control4-Style Home Controller")
api_router = APIRouter(prefix="/api")

STATE_KEY = "main"
LOG_LIMIT = 60
HLS_DIR = Path("/tmp/hls")
DAY_NAMES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "30"))
MASK_VALUE = "__stored__"
SAFE_SEG = re.compile(r"^[A-Za-z0-9._-]+$")

scheduler = AsyncIOScheduler()
_ffmpeg_proc = None
_ffmpeg_procs = {}

BUILTIN_SCENES = [
    {"id": "all_off", "name": "All Off", "desc": "Power down all TVs & mute every audio zone", "type": "critical", "icon": "Power"},
    {"id": "good_night", "name": "Good Night", "desc": "TVs off, Ecobee to 68° cool, audio muted", "type": "primary", "icon": "Moon"},
    {"id": "movie_night", "name": "Movie Night", "desc": "Apple TV 1 to Living Room TV + audio", "type": "vibrant", "icon": "Clapperboard"},
    {"id": "whole_home_audio", "name": "Whole-Home Audio", "desc": "Sync all 4 audio zones to one source", "type": "vibrant", "icon": "Radio"},
]


# Sony Bravia IPs from the UniFi client list
SONY_TV_IPS = {
    "tv_living": "192.168.0.165",
    "tv_office": "192.168.0.177",
    "tv_master": "192.168.0.78",
    "tv_guest": "192.168.0.253",
}
JTECH_HOST = "192.168.0.254"
G6_PTZ = {"ip": "192.168.0.73", "mac": "8C:ED:E1:DA:15:4F", "model": "UniFi G6 PTZ"}
PTZ_DEFAULTS = {"protect_api_key": "", "protect_user": "", "protect_password": "", "ptz_presets": "Preset 1, Preset 2, Preset 3"}
UNIFI_NVR = {"ip": "192.168.0.166", "mac": "74:FA:29:4B:01:30", "model": "UniFi Protect NVR"}
DEMO_CAM_IDS = ("cam_living", "cam_back", "cam_garage")
APPLE_TVS = {
    "atv1": {"ip": "192.168.0.145", "mac": "F0:B3:EC:35:5C:41"},
    "atv2": {"ip": "192.168.0.181", "mac": "F0:B3:EC:3D:63:5E"},
    "atv3": {"ip": "192.168.0.249", "mac": "58:D3:49:EF:E7:E2"},
    "atv4": {"ip": "192.168.0.35", "mac": "F0:B3:EC:5E:7B:B9"},
}
WS66I_HOST = "192.168.0.43"
# Physical WS66i wiring (user confirmed): 1-2 Apple TVs, 3-4 streaming modules, 5-6 unused
WS66I_INPUT_MAP = {"atv1": 1, "atv2": 2, "airplay": 3, "airplay2": 4, "spotify": 3}
WS66I_AUDIO_SOURCES = [
    {"id": "atv1", "name": "Apple TV 1"},
    {"id": "atv2", "name": "Apple TV 2"},
    {"id": "airplay", "name": "AirPlay 1"},
    {"id": "airplay2", "name": "AirPlay 2"},
    {"id": "spotify", "name": "Spotify Connect"},
]
WS66I_STREAMERS = {
    "stream_a": {"name": "Sound Amplifier", "ip": "192.168.0.213", "mac": "00:22:6C:22:18:5E", "audio_source": "airplay"},
    "stream_b": {"name": "Sound Amplifier B", "ip": "192.168.0.224", "mac": "00:22:6C:1E:6F:39", "audio_source": "airplay2"},
}
ECOBEE_LAN = {"ip": "192.168.0.222", "mac": "44:61:32:DF:C2:A9", "model": "Ecobee Smart Thermostat Premium"}
SONY_TV_MACS = {
    "tv_living": "1C:D6:BE:B3:FB:1C",
    "tv_office": "FA:8A:FD:3F:67:FC",
    "tv_master": "FA:D8:24:B4:79:2F",
    "tv_guest": "8E:BF:A2:FC:72:BF",
}

# ---------------------------------------------------------------------------
# Default apartment configuration
# ---------------------------------------------------------------------------

def default_config() -> dict:
    return {
        "matrix": {"live": False, "host": JTECH_HOST, "port": 80, "username": "admin", "password": "admin"},
        "amp": {"live": False, "host": WS66I_HOST, "streamers": copy.deepcopy(WS66I_STREAMERS), "input_map": {
**WS66I_INPUT_MAP}},
        "ecobee": {"live": False, "paired": False, **ECOBEE_LAN},
        "appletv": {"live": False, "devices": {k: {**v, "id": "", "credentials": "", "airplay_credentials": ""} for k, v in APPLE_TVS.items()}},
        "camera": {"live": False, "rtsp_url": "", **G6_PTZ, **PTZ_DEFAULTS},
        "nvr": dict(UNIFI_NVR),
        "cameras": {
        },
        "tv": {"live": False, "sets": {
            tid: {"ip": ip, "mac": SONY_TV_MACS[tid], "hdmi_input": 1, "psk": ""} for tid, ip in SONY_TV_IPS.items()
        }},
        "setup_done": False,
    }


def default_state() -> dict:
    return {
        "key": STATE_KEY,
        "property_name": "Smith Apartment",
        "sources": [
            {"id": "atv1", "name": "Apple TV 1", "input": 1, "location": "Living Room"},
            {"id": "atv2", "name": "Apple TV 2", "input": 2, "location": "Office"},
            {"id": "atv3", "name": "Apple TV 3", "input": 3, "location": "Master BR"},
            {"id": "atv4", "name": "Apple TV 4", "input": 4, "location": "Guest BR"},
        ],
        "displays": [
            {"id": "tv_living", "name": "Living Room TV", "output": 1, "source": "atv1", "power": True, "tv_volume": 30},
            {"id": "tv_office", "name": "Office TV", "output": 2, "source": "atv2", "power": False, "tv_volume": 30},
            {"id": "tv_master", "name": "Master Bedroom TV", "output": 3, "source": "atv3", "power": False, "tv_volume": 30},
            {"id": "tv_guest", "name": "Guest Room TV", "output": 4, "source": "atv4", "power": False, "tv_volume": 30},
        ],
        "audio_sources": [
            {"id": "atv1", "name": "Apple TV 1"},
            {"id": "atv2", "name": "Apple TV 2"},
            {"id": "airplay", "name": "AirPlay 1"},
            {"id": "airplay2", "name": "AirPlay 2"},
            {"id": "spotify", "name": "Spotify Connect"},
        ],
        "audio_zones": [
            {"id": "audio_living", "name": "Living Room", "amp_zone": 1, "source": "atv1", "volume": 35, "mute": False, "power": True, "paired_tv": "tv_living"},
            {"id": "audio_office", "name": "Office", "amp_zone": 2, "source": "spotify", "volume": 20, "mute": False, "power": False, "paired_tv": "tv_office"},
            {"id": "audio_master", "name": "Master Bedroom", "amp_zone": 3, "source": "airplay", "volume": 25, "mute": False, "power": False, "paired_tv": "tv_master"},
            {"id": "audio_bathroom", "name": "Bathroom", "amp_zone": 4, "source": "spotify", "volume": 30, "mute": False, "power": False, "paired_tv": None},
        ],
        "thermostat": {
            "current_temp": 72, "humidity": 45, "mode": "cool", "fan": "auto",
            "target_heat": 68, "target_cool": 74, "outdoor_temp": 75, "outdoor_condition": "Sunny",
        },
        "camera": {"id": "cam_front", "name": "Front Entry", "online": True, "motion": False, "resolution": "4K", "armed": False},
        "cameras": [
            {"id": "cam_front", "name": "Front Entry", "online": True, "motion": False},
        ],
        "network": {"unifi_online": True, "matrix_linked": True, "amp_linked": True},
        "audio_follow_tv": True,
        "away": False,
        "scenes": copy.deepcopy(BUILTIN_SCENES),
        "config": default_config(),
        "command_log": [],
    }


async def get_state() -> dict:
    doc = await db.system.find_one({"key": STATE_KEY}, {"_id": 0})
    if not doc:
        doc = default_state()
        await db.system.insert_one(copy.deepcopy(doc))
    if "config" not in doc:  # migrate older docs
        doc["config"] = default_config()
    doc.setdefault("audio_follow_tv", True)
    doc.setdefault("away", False)
    doc.pop("pin", None)  # PIN lives in db.auth, never in state
    _cfgm = doc.get("config") or {}
    for _s in ((_cfgm.get("tv") or {}).get("sets") or {}).values():  # migrate Samsung token -> Sony PSK
        if isinstance(_s, dict) and "psk" not in _s:
            _s["psk"] = _s.pop("token", "") or ""
    _cfgm.pop("smartthings", None)  # SmartThings removed (Samsung-only)
    _sets = (_cfgm.get("tv") or {}).get("sets") or {}
    for _tid, _ip in SONY_TV_IPS.items():  # fill UniFi-mapped IPs where not yet set
        if isinstance(_sets.get(_tid), dict) and not _sets[_tid].get("ip"):
            _sets[_tid]["ip"] = _ip
        if isinstance(_sets.get(_tid), dict) and not _sets[_tid].get("mac"):
            _sets[_tid]["mac"] = SONY_TV_MACS[_tid]
    doc["cameras"] = [x for x in doc.get("cameras", []) if x.get("id") not in DEMO_CAM_IDS]  # only the G6 PTZ
    for _cid in DEMO_CAM_IDS:
        (_cfgm.get("cameras") or {}).pop(_cid, None)
    if isinstance(_cfgm.get("camera"), dict):
        for _k, _v in G6_PTZ.items():
            if not _cfgm["camera"].get(_k):
                _cfgm["camera"][_k] = _v
        for _k, _v in PTZ_DEFAULTS.items():
            _cfgm["camera"].setdefault(_k, _v)
        if not _cfgm["camera"].get("webhook_token"):
            _cfgm["camera"]["webhook_token"] = _secrets.token_urlsafe(18)
    _cfgm.setdefault("nvr", dict(UNIFI_NVR))
    if isinstance(_cfgm.get("appletv"), dict):
        _devs = _cfgm["appletv"].setdefault("devices", {})
        for _aid, _a in APPLE_TVS.items():
            _d = _devs.setdefault(_aid, {})
            for _k, _v in {**_a, "id": "", "credentials": "", "airplay_credentials": ""}.items():
                if not _d.get(_k):
                    _d[_k] = _v
    if isinstance(_cfgm.get("matrix"), dict):
        if _cfgm["matrix"].get("host") in ("", None, "192.168.1.1"):
            _cfgm["matrix"]["host"] = JTECH_HOST
        _cfgm["matrix"].setdefault("username", "admin")
        if _cfgm["matrix"].get("port") in (23, "23", None, ""):
            _cfgm["matrix"]["port"] = 80  # MXT40 takes commands via its web API, not Telnet
        _cfgm["matrix"].setdefault("password", "admin")
    doc.setdefault("pinned_scenes", [LIVING_TV_PRESET["id"]])
    doc.setdefault("tunein_saved", copy.deepcopy(music.DEFAULT_STATIONS))
    for _st in doc["tunein_saved"]:
        _st["image"] = music._https(_st.get("image"))
    _cfgm.setdefault("spotify", {"client_id": "", "client_secret": "", "redirect_uri": "http://127.0.0.1:8001/api/spotify/callback"})
    if not doc.get("ws66i_wiring_v1"):  # one-time: apply the confirmed amp wiring
        doc["audio_sources"] = copy.deepcopy(WS66I_AUDIO_SOURCES)
        if isinstance(_cfgm.get("amp"), dict):
            _cfgm["amp"]["input_map"] = dict(WS66I_INPUT_MAP)
        for _z in doc.get("audio_zones", []):
            if _z.get("source") not in WS66I_INPUT_MAP:
                _z["source"] = "atv1"
        doc["ws66i_wiring_v1"] = True
        await save_state(doc)
    if isinstance(_cfgm.get("amp"), dict):
        if _cfgm["amp"].get("host") in ("", None, "192.168.1.50"):
            _cfgm["amp"]["host"] = WS66I_HOST
        _cfgm["amp"].setdefault("streamers", copy.deepcopy(WS66I_STREAMERS))
        for _sid, _st in WS66I_STREAMERS.items():
            _cfgm["amp"]["streamers"].setdefault(_sid, dict(_st)).setdefault("audio_source", _st["audio_source"])
    if isinstance(_cfgm.get("ecobee"), dict):
        for _old in ("token", "thermostat_id"):  # Ecobee cloud API retired -> HomeKit
            _cfgm["ecobee"].pop(_old, None)
        _cfgm["ecobee"].setdefault("paired", False)
        for _k, _v in ECOBEE_LAN.items():
            if not _cfgm["ecobee"].get(_k):
                _cfgm["ecobee"][_k] = _v
    for _d in doc.get("displays", []):
        if _d.get("id") == "tv_guest" and _d.get("name") == "Guest Bedroom TV":
            _d["name"] = "Guest Room TV"
    if isinstance(doc.get("camera"), dict):
        doc["camera"].setdefault("armed", False)
    if "cameras" not in doc:
        doc["cameras"] = [
            {"id": "cam_front", "name": "Front Entry", "online": True, "motion": False},
        ]
    _now = datetime.now(timezone.utc)
    for _c in doc.get("cameras", []):
        if _c.get("motion") and _c.get("motion_at"):
            try:
                if (_now - datetime.fromisoformat(_c["motion_at"])).total_seconds() > 20:
                    _c["motion"] = False
                    if _c["id"] == "cam_front" and isinstance(doc.get("camera"), dict):
                        doc["camera"]["motion"] = False
            except Exception:
                pass
    return doc


def hash_pin(pin: str) -> str:
    return bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pin_hash(pin: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pin.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


async def seed_pin():
    if not await db.auth.find_one({"key": "pin"}):
        await db.auth.insert_one({"key": "pin", "pin_hash": hash_pin(os.environ.get("DEFAULT_PIN", "1234"))})


async def create_session() -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await db.sessions.insert_one({
        "token": token,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(days=SESSION_TTL_DAYS)).isoformat(),
    })
    return token


async def valid_session(token: str) -> bool:
    if not token:
        return False
    doc = await db.sessions.find_one({"token": token})
    if not doc:
        return False
    try:
        if datetime.fromisoformat(doc["expires_at"]) < datetime.now(timezone.utc):
            await db.sessions.delete_one({"token": token})
            return False
    except Exception:
        return False
    return True


SESSION_COOKIE = "c4_session"


def _bearer(request: Request) -> str:
    """Session token from the httpOnly cookie (browser) or a Bearer header (scripts)."""
    auth = request.headers.get("Authorization", "")
    return request.cookies.get(SESSION_COOKIE) or (auth[7:] if auth.startswith("Bearer ") else "")


def _is_https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def _set_session_cookie(request: Request, response: Response, token: str):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=_is_https(request),
                        max_age=SESSION_TTL_DAYS * 86400, path="/")


def is_demo_mode(state: dict) -> bool:
    """True when no device is configured LIVE (used to gate the demo skip button)."""
    c = state.get("config") or {}
    if any((c.get(d) or {}).get("live") for d in ("matrix", "amp", "ecobee", "appletv", "camera", "tv")):
        return False
    if any((v or {}).get("live") for v in (c.get("cameras") or {}).values()):
        return False
    return True


def redact_secrets(state: dict) -> dict:
    """Never serialize integration tokens to clients; mask any set value."""
    s = copy.deepcopy(state)
    c = s.get("config") or {}

    def _mask(d, k="token"):
        if isinstance(d, dict) and d.get(k):
            d[k] = MASK_VALUE

    for tvset in ((c.get("tv") or {}).get("sets") or {}).values():
        _mask(tvset, "psk")
    _mask(c.get("matrix"), "password")
    _mask(c.get("camera"), "rtsp_url")
    _mask(c.get("camera"), "protect_api_key")
    _mask(c.get("spotify"), "client_secret")
    _mask(c.get("camera"), "protect_password")
    for _cam in (c.get("cameras") or {}).values():
        _mask(_cam, "rtsp_url")
    for _atv in ((c.get("appletv") or {}).get("devices") or {}).values():
        _mask(_atv, "credentials")
        _mask(_atv, "airplay_credentials")
    return s


def _unmask(update: dict, current: dict):
    """Drop secret fields the client echoed back as MASK_VALUE so the stored value is kept."""
    for k, v in list(update.items()):
        if isinstance(v, dict) and isinstance(current.get(k), dict):
            _unmask(v, current[k])
        elif v == MASK_VALUE:
            update.pop(k)


async def save_state(state: dict):
    state.pop("_id", None)
    await db.system.replace_one({"key": STATE_KEY}, state, upsert=True)


def log_cmd(state: dict, entry: dict):
    state["command_log"] = ([entry] + state.get("command_log", []))[:LOG_LIMIT]


def find(items, _id):
    return next((i for i in items if i["id"] == _id), None)


def cfg(state, device):
    return (state.get("config") or {}).get(device, {})


def tv_conn(state, display_id):
    t = cfg(state, "tv")
    s = (t.get("sets") or {}).get(display_id, {})
    return {**s, "live": t.get("live", False)}


def amp_input(state, source_id):
    """Physical WS66i input (1-6) wired to a logical audio source."""
    m = cfg(state, "amp").get("input_map") or {}
    try:
        return int(m.get(source_id, 1))
    except (TypeError, ValueError):
        return 1


def link_zone_to_display(state, display):
    """Sound-follows-screen: switch a room's paired audio zone to its TV's source."""
    if not state.get("audio_follow_tv", True):
        return
    zone = next((z for z in state["audio_zones"] if z.get("paired_tv") == display["id"]), None)
    if not zone:
        return
    src_id = display["source"]
    src = find(state["audio_sources"], src_id)
    if not src:
        return
    zone.update({"source": src_id, "power": True, "mute": False})
    log_cmd(state, drivers.amp.set_source(zone["amp_zone"], amp_input(state, src_id), zone["name"], src["name"], cfg(state, "amp")))


# ---------------------------------------------------------------------------
# Scene engine (shared by API + scheduler)
# ---------------------------------------------------------------------------

def apply_scene(state: dict, scene_id: str) -> bool:
    scene = find(state["scenes"], scene_id)
    if not scene:
        return False
    mc, ac, tc = cfg(state, "matrix"), cfg(state, "amp"), cfg(state, "ecobee")

    if scene_id == "all_off":
        for d in state["displays"]:
            d["power"] = False
            log_cmd(state, drivers.matrix.power(d["output"], False, d["name"], mc))
        for z in state["audio_zones"]:
            z["mute"] = True
            z["power"] = False
            log_cmd(state, drivers.amp.set_power(z["amp_zone"], False, z["name"], ac))

    elif scene_id == "good_night":
        for d in state["displays"]:
            d["power"] = False
            log_cmd(state, drivers.matrix.power(d["output"], False, d["name"], mc))
        for z in state["audio_zones"]:
            z["mute"] = True
            log_cmd(state, drivers.amp.set_mute(z["amp_zone"], True, z["name"], ac))
        state["thermostat"]["mode"] = "cool"
        state["thermostat"]["target_cool"] = 68
        log_cmd(state, drivers.thermostat.set_mode("cool", tc))
        log_cmd(state, drivers.thermostat.set_hold(state["thermostat"]["target_heat"], 68, tc, mode="cool"))

    elif scene_id == "movie_night":
        living = find(state["displays"], "tv_living")
        atv = find(state["sources"], "atv1")
        living["source"] = "atv1"
        living["power"] = True
        log_cmd(state, drivers.matrix.route(living["output"], atv["input"], living["name"], atv["name"], mc))
        az = find(state["audio_zones"], "audio_living")
        az.update({"source": "atv1", "power": True, "mute": False, "volume": 45})
        log_cmd(state, drivers.amp.set_source(az["amp_zone"], amp_input(state, "atv1"), az["name"], atv["name"], ac))

    elif scene_id == "whole_home_audio":
        for z in state["audio_zones"]:
            z.update({"source": "spotify", "power": True, "mute": False, "volume": 30})
            log_cmd(state, drivers.amp.set_source(z["amp_zone"], amp_input(state, "spotify"), z["name"], "Spotify Connect", ac))
    return True


async def run_scene_by_id(scene_id: str, trigger_note: str = ""):
    state = await get_state()
    if await apply_scene_any(state, scene_id):
        if trigger_note:
            log_cmd(state, {"driver": "Automation", "transport": "scheduler", "command": scene_id,
                            "note": trigger_note, "timestamp": drivers._ts(), "status": "sent"})
        await save_state(state)


def apply_snapshot(state: dict, snap: dict):
    """Apply a user-created scene captured from a previous system state."""
    mc, ac, tc = cfg(state, "matrix"), cfg(state, "amp"), cfg(state, "ecobee")
    for ds in snap.get("displays", []):
        d = find(state["displays"], ds["id"])
        if not d:
            continue
        d["power"], d["source"] = ds["power"], ds["source"]
        if ds["power"]:
            src = find(state["sources"], ds["source"])
            if src:
                log_cmd(state, drivers.matrix.route(d["output"], src["input"], d["name"], src["name"], mc))
        else:
            log_cmd(state, drivers.matrix.power(d["output"], False, d["name"], mc))
    for zs in snap.get("audio_zones", []):
        z = find(state["audio_zones"], zs["id"])
        if not z:
            continue
        for k in ("source", "volume", "mute", "power"):
            if k in zs:
                z[k] = zs[k]
        src = find(state["audio_sources"], z["source"])
        log_cmd(state, drivers.amp.set_source(z["amp_zone"], amp_input(state, z["source"]), z["name"], src["name"] if src else z["source"], ac))
    t = snap.get("thermostat")
    if t:
        state["thermostat"].update(t)
        log_cmd(state, drivers.thermostat.set_mode(state["thermostat"]["mode"], tc))
        log_cmd(state, drivers.thermostat.set_hold(state["thermostat"]["target_heat"], state["thermostat"]["target_cool"], tc, mode=state["thermostat"]["mode"]))


# Preset steps: executed in order. TV-on first so later TV steps reach a powered set.
PRESET_ACTIONS = {
    "tv_power": ("display", "bool"), "tv_route": ("display", "source"), "tv_volume": ("display", "level"),
    "amp_source": ("zone", "audio_source"), "amp_volume": ("zone", "level"), "amp_power": ("zone", "bool"),
    "stream_preset": ("streamer", "preset"),
    "tunein_station": ("streamer", "station"),
    "spotify_play": ("streamer", "spotify_uri"),
}
TV_WAKE_DELAY_S = 6
LIVING_TV_PRESET = {
    "id": "preset_living_tv_sound", "name": "Watch TV in Living Room with Sound", "icon": "Tv", "type": "vibrant",
    "custom": True, "desc": "Living TV on · Apple TV 1 · TV muted to 0 · speakers on input 1",
    "actions": [
        {"type": "tv_power", "target": "tv_living", "value": True},
        {"type": "tv_route", "target": "tv_living", "value": "atv1"},
        {"type": "tv_volume", "target": "tv_living", "value": 0},
        {"type": "amp_source", "target": "audio_living", "value": "atv1"},
    ],
}


def _tv_sound_preset(pid, room, tv, zone, atv, atv_name):
    return {"id": pid, "name": f"Watch TV in {room} with Sound", "icon": "Tv", "type": "vibrant", "custom": True,
            "desc": f"{room} TV on · {atv_name} · TV muted to 0 · speakers on {atv_name}",
            "actions": [{"type": "tv_power", "target": tv, "value": True},
                        {"type": "tv_route", "target": tv, "value": atv},
                        {"type": "tv_volume", "target": tv, "value": 0},
                        {"type": "amp_source", "target": zone, "value": atv}]}


ROOM_PRESETS = [
    _tv_sound_preset("preset_office_tv_sound", "Office", "tv_office", "audio_office", "atv2", "Apple TV 2"),
    _tv_sound_preset("preset_master_tv_sound", "Master Bedroom", "tv_master", "audio_master", "atv2", "Apple TV 2"),
    {"id": "preset_bathroom_audio", "name": "Bathroom Audio", "icon": "Radio", "type": "vibrant", "custom": True,
     "desc": "Bathroom speakers play Apple TV 2 (same as the Master Bedroom TV)",
     "actions": [{"type": "amp_source", "target": "audio_bathroom", "value": "atv2"}]},
]
ALL_ZONES = ["audio_living", "audio_office", "audio_master", "audio_bathroom"]
GAME_DAY_PRESET = {
    "id": "preset_yankees_wfan", "name": "Yankees on WFAN", "icon": "Radio", "type": "vibrant", "custom": True,
    "desc": "WFAN on Stream 1 · every room at 40%",
    "actions": [{"type": "tunein_station", "target": "stream_a", "value": "wfan"}]
    + [{"type": "amp_source", "target": z, "value": "airplay"} for z in ALL_ZONES]
    + [{"type": "amp_volume", "target": z, "value": 40} for z in ALL_ZONES],
}
MORNING_PRESET = {
    "id": "preset_morning_brief", "name": "Morning Market Brief", "icon": "Coffee", "type": "vibrant", "custom": True,
    "desc": "Bloomberg Radio on Stream 2 · Office at 20%",
    "actions": [{"type": "tunein_station", "target": "stream_b", "value": "s165740"},
                {"type": "amp_source", "target": "audio_office", "value": "airplay2"},
                {"type": "amp_volume", "target": "audio_office", "value": 20}],
}
MORNING_AUTOMATION = {"id": "auto_morning_brief", "name": "Morning Market Brief · weekdays 8:00", "enabled": True,
                      "trigger": {"type": "schedule", "time": "08:00", "days": [1, 2, 3, 4, 5]},
                      "action": {"scene_id": "preset_morning_brief"}}


def validate_actions(state: dict, actions: list) -> list:
    if not actions:
        raise HTTPException(400, "Add at least one step")
    out = []
    streamers = [{"id": k} for k in (cfg(state, "amp").get("streamers") or {})]
    lists = {"display": state["displays"], "zone": state["audio_zones"], "source": state["sources"],
             "audio_source": state["audio_sources"], "streamer": streamers}
    for a in actions:
        kind = PRESET_ACTIONS.get(a.get("type"))
        if not kind:
            raise HTTPException(400, f"Unknown step type {a.get('type')}")
        if not find(lists[kind[0]], a.get("target")):
            raise HTTPException(400, f"Unknown {kind[0]} {a.get('target')}")
        v = a.get("value")
        if kind[1] == "bool":
            v = bool(v)
        elif kind[1] == "level":
            if not isinstance(v, (int, float)) or not 0 <= v <= 100:
                raise HTTPException(400, "Volume must be 0-100")
            v = int(v)
        elif kind[1] == "station":
            if not find(state.get("tunein_saved", []), v):
                raise HTTPException(400, f"Unknown saved station {v}")
        elif kind[1] == "spotify_uri":
            if not (isinstance(v, str) and re.match(r"^spotify:(playlist|album|artist|show):[A-Za-z0-9]+$", v)):
                raise HTTPException(400, "Invalid Spotify link")
        elif kind[1] == "preset":
            if not isinstance(v, int) or not 1 <= v <= 12:
                raise HTTPException(400, "Favourite number must be 1-12")
        elif not find(lists[kind[1]], v):
            raise HTTPException(400, f"Unknown {kind[1]} {v}")
        step = {"type": a["type"], "target": a["target"], "value": v}
        if a.get("label"):
            step["label"] = str(a["label"])[:80]
        out.append(step)
    return out


async def apply_actions(state: dict, actions: list):
    mc, ac = cfg(state, "matrix"), cfg(state, "amp")
    woke = set()
    for a in actions:
        t, tgt, v = a["type"], a["target"], a["value"]
        if t.startswith("tv_"):
            d = find(state["displays"], tgt)
            if not d:
                continue
            if t == "tv_power":
                d["power"] = v
                log_cmd(state, drivers.matrix.power(d["output"], v, d["name"], mc))
                log_cmd(state, await asyncio.to_thread(drivers.tv.power, d["name"], v, tv_conn(state, d["id"]), True))
                if v:
                    woke.add(d["id"])
            elif t == "tv_route":
                src = find(state["sources"], v)
                d["source"], d["power"] = v, True
                log_cmd(state, drivers.matrix.route(d["output"], src["input"], d["name"], src["name"], mc))
            elif t == "tv_volume":
                if d["id"] in woke and tv_conn(state, d["id"]).get("live"):
                    await asyncio.sleep(TV_WAKE_DELAY_S)  # Sony needs a few seconds after Wake-on-LAN
                    woke.discard(d["id"])
                d["tv_volume"] = v
                log_cmd(state, await asyncio.to_thread(drivers.tv.set_volume, d["name"], v, tv_conn(state, d["id"])))
        elif t == "stream_preset":
            await stream_play_preset(state, tgt, v)
        elif t == "tunein_station":
            await stream_play_station(state, tgt, find(state.get("tunein_saved", []), v))
        elif t == "spotify_play":
            await stream_play_spotify(state, tgt, v, a.get("label") or v)
        else:
            z = find(state["audio_zones"], tgt)
            if not z:
                continue
            if t == "amp_source":
                src = find(state["audio_sources"], v)
                z.update({"source": v, "power": True, "mute": False})
                log_cmd(state, drivers.amp.set_source(z["amp_zone"], amp_input(state, v), z["name"], src["name"], ac))
            elif t == "amp_volume":
                z["volume"] = v
                log_cmd(state, drivers.amp.set_volume(z["amp_zone"], round(v * 38 / 100), z["name"], v, ac))
            elif t == "amp_power":
                z["power"] = v
                log_cmd(state, drivers.amp.set_power(z["amp_zone"], v, z["name"], ac))


async def apply_scene_any(state: dict, scene_id: str) -> bool:
    if apply_scene(state, scene_id):
        return True
    doc = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    if not doc:
        return False
    if doc.get("actions"):
        await apply_actions(state, doc["actions"])
    else:
        apply_snapshot(state, doc["snapshot"])
    return True


# ---------------------------------------------------------------------------
# Automations + scheduler
# ---------------------------------------------------------------------------

def _register_job(auto: dict):
    job_id = auto["id"]
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass
    if not auto.get("enabled"):
        return
    trig = auto.get("trigger", {})
    if trig.get("type") != "schedule":
        return
    hh, mm = (trig.get("time") or "08:00").split(":")
    days = trig.get("days") or [0, 1, 2, 3, 4, 5, 6]
    dow = ",".join(DAY_NAMES[d] for d in days) if days else "*"
    scene_id = auto["action"]["scene_id"]
    scheduler.add_job(
        run_scene_by_id, "cron", id=job_id, replace_existing=True,
        day_of_week=dow, hour=int(hh), minute=int(mm),
        args=[scene_id, f"Automation '{auto['name']}'"],
    )


async def reload_jobs():
    for j in scheduler.get_jobs():
        if j.id not in ("offline_watch", "prune_sessions"):
            j.remove()
    autos = await db.automations.find({}, {"_id": 0}).to_list(200)
    for a in autos:
        _register_job(a)


class Automation(BaseModel):
    name: str
    enabled: bool = True
    trigger: dict   # {type:'schedule', time:'22:00', days:[0..6]} | {type:'event', event:'motion'}
    action: dict    # {scene_id:'good_night'}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PinReq(BaseModel):
    pin: str

class ChangePinReq(BaseModel):
    current: str
    new_pin: str

class RouteReq(BaseModel):
    display_id: str
    source_id: str

class BroadcastReq(BaseModel):
    source_id: str

class DisplayPowerReq(BaseModel):
    display_id: str
    power: bool

class RemoteReq(BaseModel):
    source_id: str
    key: str

class TvVolumeReq(BaseModel):
    display_id: str
    volume: int

class ZoneReq(BaseModel):
    zone_id: str
    source: Optional[str] = None
    volume: Optional[int] = None
    mute: Optional[bool] = None
    power: Optional[bool] = None

class AudioGroupReq(BaseModel):
    source_id: str
    volume: int

class ClimateReq(BaseModel):
    mode: Optional[str] = None
    fan: Optional[str] = None
    target_heat: Optional[int] = None
    target_cool: Optional[int] = None

class ConfigReq(BaseModel):
    config: dict

class ToggleReq(BaseModel):
    enabled: bool

class SceneCreateReq(BaseModel):
    name: str
    icon: Optional[str] = "Sparkles"
    type: Optional[str] = "vibrant"


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Control4-Style Home Controller API"}


PIN_LOCK_THRESHOLD = 5
PIN_LOCK_SECONDS = 30


@api_router.post("/auth/pin")
async def verify_pin(req: PinReq, request: Request, response: Response):
    doc = await db.auth.find_one({"key": "pin"})
    if not doc:
        await seed_pin()
        doc = await db.auth.find_one({"key": "pin"})
    now = datetime.now(timezone.utc)
    locked_until = doc.get("locked_until")
    if locked_until:
        lu = datetime.fromisoformat(locked_until)
        if lu > now:
            return {"success": False, "locked": True, "retry_after": int((lu - now).total_seconds()) + 1, "attempts_left": 0}
    if verify_pin_hash(req.pin, doc["pin_hash"]):
        await db.auth.update_one({"key": "pin"}, {"$set": {"fails": 0}, "$unset": {"locked_until": ""}})
        _set_session_cookie(request, response, await create_session())
        return {"success": True}
    fails = int(doc.get("fails", 0)) + 1
    update = {"fails": fails}
    resp = {"success": False, "locked": False, "attempts_left": max(0, PIN_LOCK_THRESHOLD - fails)}
    if fails >= PIN_LOCK_THRESHOLD:
        secs = min(PIN_LOCK_SECONDS * (2 ** (fails - PIN_LOCK_THRESHOLD)), 300)
        update["locked_until"] = (now + timedelta(seconds=secs)).isoformat()
        resp.update({"locked": True, "retry_after": secs, "attempts_left": 0})
    await db.auth.update_one({"key": "pin"}, {"$set": update})
    return resp


@api_router.post("/auth/change-pin")
async def change_pin(req: ChangePinReq, request: Request):
    doc = await db.auth.find_one({"key": "pin"})
    if not doc or not verify_pin_hash(req.current, doc["pin_hash"]):
        raise HTTPException(400, "Current PIN is incorrect")
    if not (req.new_pin.isdigit() and len(req.new_pin) == 4):
        raise HTTPException(400, "New PIN must be exactly 4 digits")
    await db.auth.update_one({"key": "pin"}, {"$set": {"pin_hash": hash_pin(req.new_pin), "fails": 0}, "$unset": {"locked_until": ""}})
    await db.sessions.delete_many({"token": {"$ne": _bearer(request)}})  # sign out every other panel
    return {"success": True}


@api_router.post("/auth/demo")
async def demo_login(request: Request, response: Response):
    state = await get_state()
    if not is_demo_mode(state):
        raise HTTPException(403, "Demo bypass is disabled once real devices are configured")
    _set_session_cookie(request, response, await create_session())
    return {"success": True}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = _bearer(request)
    if token:
        await db.sessions.delete_one({"token": token})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@api_router.get("/bootstrap")
async def bootstrap():
    state = await get_state()
    return {"property_name": state.get("property_name"), "demo_mode": is_demo_mode(state)}


@api_router.get("/state")
async def read_state():
    return redact_secrets(await get_state())


@api_router.post("/state/reset")
async def reset_state():
    fresh = default_state()
    await save_state(fresh)
    return redact_secrets(fresh)


@api_router.post("/matrix/route")
async def matrix_route(req: RouteReq):
    state = await get_state()
    display, source = find(state["displays"], req.display_id), find(state["sources"], req.source_id)
    if not display or not source:
        raise HTTPException(404, "Display or source not found")
    display["source"], display["power"] = source["id"], True
    log_cmd(state, drivers.matrix.route(display["output"], source["input"], display["name"], source["name"], cfg(state, "matrix")))
    link_zone_to_display(state, display)
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/matrix/broadcast")
async def matrix_broadcast(req: BroadcastReq):
    state = await get_state()
    source = find(state["sources"], req.source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    mc = cfg(state, "matrix")
    for display in state["displays"]:
        display["source"], display["power"] = source["id"], True
        log_cmd(state, drivers.matrix.route(display["output"], source["input"], display["name"], source["name"], mc))
        link_zone_to_display(state, display)
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/display/power")
async def display_power(req: DisplayPowerReq):
    state = await get_state()
    display = find(state["displays"], req.display_id)
    if not display:
        raise HTTPException(404, "Display not found")
    display["power"] = req.power
    log_cmd(state, await asyncio.to_thread(drivers.tv.power, display["name"], req.power, tv_conn(state, display["id"]), True))
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/display/tvvolume")
async def display_tvvolume(req: TvVolumeReq):
    state = await get_state()
    display = find(state["displays"], req.display_id)
    if not display:
        raise HTTPException(404, "Display not found")
    vol = max(0, min(100, req.volume))
    display["tv_volume"] = vol
    log_cmd(state, await asyncio.to_thread(drivers.tv.set_volume, display["name"], vol, tv_conn(state, display["id"])))
    await save_state(state)
    return {"ok": True, "tv_volume": vol, "command_log": state["command_log"]}


@api_router.post("/display/tvkey")
async def display_tvkey(req: RemoteReq):
    state = await get_state()
    display = find(state["displays"], req.source_id)
    if not display:
        raise HTTPException(404, "Display not found")
    log_cmd(state, drivers.tv.key(display["name"], req.key, tv_conn(state, display["id"])))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


@api_router.post("/display/remote")
async def display_remote(req: RemoteReq):
    state = await get_state()
    source = find(state["sources"], req.source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    log_cmd(state, drivers.appletv.key(source["name"], req.key, cfg(state, "appletv"), device=source["id"]))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


class MatrixIdentifyReq(BaseModel):
    input: int
    output: int


class MatrixMapReq(BaseModel):
    outputs: dict = {}
    inputs: dict = {}


@api_router.post("/matrix/identify")
async def matrix_identify(req: MatrixIdentifyReq):
    if not (1 <= req.input <= 4 and 1 <= req.output <= 4):
        raise HTTPException(400, "input/output must be 1-4")
    state = await get_state()
    entry = drivers.matrix.route(req.output, req.input, f"Output {req.output}", f"Input {req.input}", cfg(state, "matrix"))
    log_cmd(state, entry)
    await save_state(state)
    return {"ok": entry.get("status") != "error", "status": entry.get("status"), "error": entry.get("error")}


def _apply_map(items: list, mapping: dict, field: str):
    known = {x["id"] for x in items}
    if not set(mapping) <= known:
        raise HTTPException(400, f"Unknown id(s): {sorted(set(mapping) - known)}")
    merged = {x["id"]: x[field] for x in items}
    for k, v in mapping.items():
        if not isinstance(v, int) or not 1 <= v <= 4:
            raise HTTPException(400, f"{field} for {k} must be 1-4")
        merged[k] = v
    if len(set(merged.values())) != len(merged):
        raise HTTPException(400, f"Each {field} number can only be used once")
    for x in items:
        x[field] = merged[x["id"]]


@api_router.put("/matrix/map")
async def matrix_map(req: MatrixMapReq):
    state = await get_state()
    _apply_map(state["displays"], req.outputs, "output")
    _apply_map(state["sources"], req.inputs, "input")
    state["matrix_wiring_confirmed"] = True
    await save_state(state)
    return redact_secrets(state)


# ---------------------------------------------------------------------------
# First-night checklist: auto-detected steps + manual ticks
CHECKLIST_MANUAL_IDS = {"install", "ipad_wifi", "tv_setup", "ptz_presets", "remote_access"}


class ChecklistTickReq(BaseModel):
    done: bool


@api_router.get("/checklist")
async def checklist():
    state = await get_state()
    c = state["config"]
    health = await device_health()
    online = {d["id"]: d["online"] for d in health["devices"]}
    pin_doc = await db.auth.find_one({"key": "pin"}) or {}
    pin_changed = bool(pin_doc.get("pin_hash")) and not verify_pin_hash(os.environ.get("DEFAULT_PIN", "1234"), pin_doc["pin_hash"])
    tv_sets = (c.get("tv") or {}).get("sets") or {}
    tv_keys = sum(1 for t in tv_sets.values() if t.get("psk"))
    manual = state.get("checklist_manual") or {}
    items = [
        ("install", "Install", "App running on the mini-PC", "Follow the Windows setup guide; open http://192.168.0.10:3000 on the iPad.", any(online.values()) or None, "setup-guide-link"),
        ("ipad_wifi", "Install", "iPad on home Wi-Fi, added to Home Screen", "Safari → Share → Add to Home Screen for full-screen mode.", None, None),
        ("pin", "Install", "Unlock PIN changed from 1234", "Pick a new 4-digit code.", pin_changed, "settings-pin"),
        ("tv_setup", "Video", f"Sony TVs: pre-shared key + Remote start ({tv_keys}/4 keys entered)", "On each TV: Network → IP control → PSK; Remote start ON.", (tv_keys == 4 and bool((c.get("tv") or {}).get("live"))) or None, "settings-tv"),
        ("amp_live", "Audio", "WS66i amp set to Live", "192.168.0.43; room sources are set in Settings → Rooms & sources.", bool((c.get("amp") or {}).get("live")), "settings-amp"),
        ("ecobee_paired", "Sources & climate", "Thermostat paired over HomeKit", "Enter the 8-digit HomeKit code from the thermostat (Menu → Settings → HomeKit).", bool((c.get("ecobee") or {}).get("paired")), "settings-ecobee"),
        ("cam_stream", "Camera", "Camera stream link added", "Protect → G6 PTZ → Settings → Advanced → RTSPS (Medium).", bool((c.get("camera") or {}).get("rtsp_url")), "settings-camera"),
        ("cam_apikey", "Camera", "Protect API key added", "Protect → Settings → Control Plane → Integrations.", bool((c.get("camera") or {}).get("protect_api_key")), "settings-camera"),
        ("ptz_presets", "Camera", "PTZ presets saved and named", "Save positions in Protect, then list their names in Settings.", None, "settings-camera"),
        ("all_green", "Finish", f"All devices green in Device health ({health['online']}/{health['total']})", "Fix anything red before relying on shortcuts.", health["total"] > 0 and health["online"] == health["total"], "health"),
        ("remote_access", "Finish", "Remote access via UniFi Teleport / WireGuard", "Never port-forward the controller.", None, None),
    ]
    out = []
    for iid, group, title, hint, auto, target in items:
        done = bool(auto) or bool(manual.get(iid))
        out.append({"id": iid, "group": group, "title": title, "hint": hint, "auto": bool(auto),
                    "manual_allowed": iid in CHECKLIST_MANUAL_IDS, "done": done, "target": target})
    return {"items": out, "done": sum(1 for i in out if i["done"]), "total": len(out)}


@api_router.post("/checklist/{item_id}")
async def checklist_tick(item_id: str, req: ChecklistTickReq):
    if item_id not in CHECKLIST_MANUAL_IDS:
        raise HTTPException(400, "This step is detected automatically")
    state = await get_state()
    state.setdefault("checklist_manual", {})[item_id] = req.done
    await save_state(state)
    return await checklist()


@api_router.post("/audio/zone")
async def audio_zone(req: ZoneReq):
    state = await get_state()
    zone = find(state["audio_zones"], req.zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    ac = cfg(state, "amp")
    if req.source is not None:
        src = find(state["audio_sources"], req.source)
        if not src:
            raise HTTPException(404, "Audio source not found")
        zone["source"], zone["power"] = req.source, True
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], amp_input(state, req.source), zone["name"], src["name"], ac))
    if req.volume is not None:
        zone["volume"] = max(0, min(100, req.volume))
        log_cmd(state, drivers.amp.set_volume(zone["amp_zone"], round(zone["volume"] * 38 / 100), zone["name"], zone["volume"], ac))
    if req.mute is not None:
        zone["mute"] = req.mute
        log_cmd(state, drivers.amp.set_mute(zone["amp_zone"], req.mute, zone["name"], ac))
    if req.power is not None:
        zone["power"] = req.power
        log_cmd(state, drivers.amp.set_power(zone["amp_zone"], req.power, zone["name"], ac))
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/audio/group")
async def audio_group(req: AudioGroupReq):
    state = await get_state()
    src = find(state["audio_sources"], req.source_id)
    if not src:
        raise HTTPException(404, "Audio source not found")
    ac = cfg(state, "amp")
    vol = max(0, min(100, req.volume))
    for zone in state["audio_zones"]:
        zone.update({"source": req.source_id, "volume": vol, "mute": False, "power": True})
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], amp_input(state, req.source_id), zone["name"], src["name"], ac))
        log_cmd(state, drivers.amp.set_volume(zone["amp_zone"], round(vol * 38 / 100), zone["name"], vol, ac))
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/climate")
async def climate(req: ClimateReq):
    state = await get_state()
    t, tc = state["thermostat"], cfg(state, "ecobee")
    if req.mode is not None:
        t["mode"] = req.mode
        log_cmd(state, await asyncio.to_thread(drivers.thermostat.set_mode, req.mode, tc))
    if req.fan is not None:
        t["fan"] = req.fan
        log_cmd(state, await asyncio.to_thread(drivers.thermostat.set_fan, req.fan, tc))
    if req.target_heat is not None or req.target_cool is not None:
        if req.target_heat is not None:
            t["target_heat"] = max(45, min(90, req.target_heat))
        if req.target_cool is not None:
            t["target_cool"] = max(45, min(95, req.target_cool))
        log_cmd(state, await asyncio.to_thread(drivers.thermostat.set_hold, t["target_heat"], t["target_cool"], tc, t["mode"]))
    await save_state(state)
    return redact_secrets(state)


class HomeKitPairReq(BaseModel):
    code: str


@api_router.post("/homekit/pair")
async def homekit_pair(req: HomeKitPairReq):
    state = await get_state()
    ec = state["config"]["ecobee"]
    if not ec.get("ip"):
        raise HTTPException(400, "Set the thermostat LAN IP first")
    try:
        data = await asyncio.to_thread(homekit.thermostat.pair, ec["ip"], req.code)
    except Exception as e:
        raise HTTPException(400, f"Pairing failed: {str(e)[:200]}")
    await db.homekit.replace_one({"key": "ecobee"}, {"key": "ecobee", "pairing": data}, upsert=True)
    ec.update({"paired": True, "live": True})
    log_cmd(state, {"driver": "Ecobee", "transport": "HomeKit HAP/IP (LAN)", "command": "pair-setup",
                    "note": f"Paired with thermostat @ {ec['ip']}", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return redact_secrets(state)


@api_router.delete("/homekit/pair")
async def homekit_unpair():
    state = await get_state()
    try:
        await asyncio.to_thread(homekit.thermostat.unpair)
    except Exception as e:
        logging.getLogger(__name__).warning("HomeKit unpair: %s", e)
    await db.homekit.delete_one({"key": "ecobee"})
    state["config"]["ecobee"].update({"paired": False, "live": False})
    await save_state(state)
    return redact_secrets(state)


def _apply_homekit_reading(t: dict, r: dict):
    if r.get("current_temp") is not None:
        t["current_temp"] = homekit.c_to_f(r["current_temp"])
    if r.get("humidity") is not None:
        t["humidity"] = round(r["humidity"])
    if r.get("target_state") in homekit.HAP_TO_MODE:
        t["mode"] = homekit.HAP_TO_MODE[r["target_state"]]
    if r.get("heat_threshold") is not None:
        t["target_heat"] = homekit.c_to_f(r["heat_threshold"])
    if r.get("cool_threshold") is not None:
        t["target_cool"] = homekit.c_to_f(r["cool_threshold"])
    if r.get("target_temp") is not None and t.get("mode") in ("heat", "cool"):
        t["target_heat" if t["mode"] == "heat" else "target_cool"] = homekit.c_to_f(r["target_temp"])
    if r.get("target_fan") is not None:
        t["fan"] = "auto" if r["target_fan"] == 1 else "on"


@api_router.post("/climate/refresh")
async def climate_refresh():
    state = await get_state()
    ec = cfg(state, "ecobee")
    if not (ec.get("live") and ec.get("paired")):
        return {"live": False, "state": redact_secrets(state)}
    try:
        reading = await asyncio.to_thread(homekit.thermostat.read)
    except Exception as e:
        return {"live": True, "ok": False, "error": str(e)[:200], "state": redact_secrets(state)}
    _apply_homekit_reading(state["thermostat"], reading)
    await save_state(state)
    return {"live": True, "ok": True, "state": redact_secrets(state)}


@api_router.post("/scene/{scene_id}")
async def run_scene(scene_id: str):
    state = await get_state()
    if not await apply_scene_any(state, scene_id):
        raise HTTPException(404, "Scene not found")
    await save_state(state)
    return redact_secrets(state)


@api_router.get("/scenes")
async def list_scenes():
    customs = await db.scenes.find({}, {"_id": 0}).to_list(200)
    return copy.deepcopy(BUILTIN_SCENES) + customs


@api_router.post("/scenes")
async def create_scene(req: SceneCreateReq):
    state = await get_state()
    snap = {
        "displays": [{"id": d["id"], "power": d["power"], "source": d["source"]} for d in state["displays"]],
        "audio_zones": [{"id": z["id"], "source": z["source"], "volume": z["volume"], "mute": z["mute"], "power": z["power"]} for z in state["audio_zones"]],
        "thermostat": {k: state["thermostat"][k] for k in ("mode", "fan", "target_heat", "target_cool")},
    }
    doc = {"id": str(uuid.uuid4()), "name": req.name.strip(), "desc": "Custom scene · snapshot", "icon": req.icon, "type": req.type, "custom": True, "snapshot": snap}
    await db.scenes.insert_one(copy.deepcopy(doc))
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Streaming modules (Linkplay) — favourites, transport, now playing, room mapping
DEMO_FAVOURITES = ["Jazz24 Radio", "Discover Weekly", "Chill Vibes", "NPR News", "Classical KUSC", "Morning Acoustic"]


def _streamer(state, sid):
    st = (cfg(state, "amp").get("streamers") or {}).get(sid)
    if not st:
        raise HTTPException(404, "Streaming module not found")
    return st


def _stream_live(state):
    return bool(cfg(state, "amp").get("live"))


def _sim(state, sid):
    return state.setdefault("stream_sim", {}).setdefault(sid, {"status": "stop", "title": "", "artist": "", "vol": 60, "preset": None})


async def stream_play_preset(state, sid, number):
    st = _streamer(state, sid)
    entry = {"driver": "Linkplay", "transport": "HTTP API", "command": f"MCUKeyShortClick:{number}",
             "note": f"{st['name']} play favourite {number}", "timestamp": drivers._ts(), "status": "simulated"}
    if _stream_live(state):
        try:
            await linkplay.play_preset(st["ip"], number)
            entry["status"] = "sent"
        except Exception as e:
            entry.update({"status": "error", "error": str(e)[:200]})
    else:
        sim = _sim(state, sid)
        name = DEMO_FAVOURITES[(number - 1) % len(DEMO_FAVOURITES)]
        sim.update({"status": "play", "title": name, "artist": "Demo stream", "preset": number})
    log_cmd(state, entry)
    return entry


def _zones_on(state, audio_source):
    return [z["id"] for z in state["audio_zones"] if z.get("source") == audio_source and z.get("power")]


class StreamPlayReq(BaseModel):
    preset: Optional[int] = None
    zones: List[str] = []


class StreamCmdReq(BaseModel):
    cmd: str
    value: Optional[int] = None


@api_router.get("/stream/status")
async def stream_status():
    state = await get_state()
    live = _stream_live(state)
    names = {x["id"]: x["name"] for x in state["audio_sources"]}
    out = []
    for i, (sid, st) in enumerate((cfg(state, "amp").get("streamers") or {}).items()):
        src = st.get("audio_source")
        item = {"id": sid, "label": f"Stream {i + 1}", "name": st.get("name", sid), "ip": st.get("ip"), "audio_source": src,
                "source_name": names.get(src, src), "input": amp_input(state, src), "zones": _zones_on(state, src), "live": live}
        if live:
            try:
                item.update(await linkplay.status(st["ip"]), online=True)
            except Exception as e:
                item.update(online=False, error=str(e)[:120], status="offline")
        else:
            sim = _sim(state, sid)
            item.update(online=True, status=sim["status"], title=sim["title"], artist=sim["artist"], album="", art="", vol=sim["vol"])
        out.append(item)
    return {"modules": out}


@api_router.get("/stream/{sid}/presets")
async def stream_presets(sid: str):
    state = await get_state()
    st = _streamer(state, sid)
    if not _stream_live(state):
        return {"presets": [{"number": i + 1, "name": n, "source": "Demo", "art": ""} for i, n in enumerate(DEMO_FAVOURITES)]}
    try:
        return {"presets": await linkplay.presets(st["ip"])}
    except Exception as e:
        raise HTTPException(424, f"{e}")


@api_router.post("/stream/{sid}/play")
async def stream_play(sid: str, req: StreamPlayReq):
    state = await get_state()
    st = _streamer(state, sid)
    for zid in req.zones:
        if not find(state["audio_zones"], zid):
            raise HTTPException(400, f"Unknown zone {zid}")
    if req.preset is not None:
        if not 1 <= req.preset <= 12:
            raise HTTPException(400, "Favourite number must be 1-12")
        entry = await stream_play_preset(state, sid, req.preset)
        if entry["status"] == "error":
            await save_state(state)
            raise HTTPException(424, entry["error"])
    src_id = st.get("audio_source")
    src = find(state["audio_sources"], src_id)
    ac = cfg(state, "amp")
    for zid in req.zones:
        z = find(state["audio_zones"], zid)
        z.update({"source": src_id, "power": True, "mute": False})
        log_cmd(state, drivers.amp.set_source(z["amp_zone"], amp_input(state, src_id), z["name"], src["name"] if src else src_id, ac))
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/stream/{sid}/cmd")
async def stream_cmd(sid: str, req: StreamCmdReq):
    if req.cmd not in linkplay.CMDS and req.cmd != "volume":
        raise HTTPException(400, "Unknown command")
    state = await get_state()
    st = _streamer(state, sid)
    if _stream_live(state):
        try:
            await linkplay.command(st["ip"], req.cmd, req.value)
        except Exception as e:
            raise HTTPException(424, f"{e}")
    else:
        sim = _sim(state, sid)
        if req.cmd == "volume":
            sim["vol"] = max(0, min(100, int(req.value or 0)))
        elif req.cmd in ("play_pause",):
            sim["status"] = "pause" if sim["status"] == "play" else "play"
        elif req.cmd in ("pause", "stop"):
            sim["status"] = req.cmd
        elif req.cmd == "play":
            sim["status"] = "play"
    log_cmd(state, {"driver": "Linkplay", "transport": "HTTP API", "command": req.cmd if req.cmd != "volume" else f"vol:{req.value}",
                    "note": f"{st['name']} {req.cmd}", "timestamp": drivers._ts(), "status": "sent" if _stream_live(state) else "simulated"})
    await save_state(state)
    return {"ok": True}


# ---------------------------------------------------------------------------
# TuneIn + Spotify on the streaming modules
async def _stream_entry(state, sid, command, note, live_fn, sim_title, sim_artist):
    st = _streamer(state, sid)
    entry = {"driver": "Linkplay", "transport": "HTTP API", "command": command, "note": f"{st['name']} {note}",
             "timestamp": drivers._ts(), "status": "simulated"}
    if _stream_live(state):
        try:
            await live_fn(st)
            entry["status"] = "sent"
        except Exception as e:
            entry.update({"status": "error", "error": str(e)[:200]})
    else:
        _sim(state, sid).update({"status": "play", "title": sim_title, "artist": sim_artist, "preset": None})
    log_cmd(state, entry)
    return entry


async def stream_play_station(state, sid, station):
    if not station:
        raise HTTPException(404, "Station not found")

    async def go(st):
        url = await music.resolve(station)
        await linkplay._get(st["ip"], music.stream_command(url))
    return await _stream_entry(state, sid, f"play TuneIn {station.get('guide_id') or 'url'}", f"play {station['name']}",
                               go, station["name"], station.get("category") or "Radio")


async def _spotify_session():
    tok = await db.spotify.find_one({"key": "token"}, {"_id": 0})
    if not tok:
        raise HTTPException(400, "Spotify is not connected")
    conf = (await get_state())["config"].get("spotify") or {}
    sp, fresh = await music.run(music.client, conf, tok["token"])
    if fresh is not tok["token"]:
        await db.spotify.update_one({"key": "token"}, {"$set": {"token": fresh}})
    return sp


async def stream_play_spotify(state, sid, uri, label):
    async def go(st):
        sp = await _spotify_session()
        try:
            await music.run(music.play_on, sp, st.get("spotify_name") or st["name"], uri)
        except spotify_exc() as e:
            if e.http_status == 403:
                raise RuntimeError("Spotify Premium is required to start music on a speaker")
            raise RuntimeError(e.msg)
    return await _stream_entry(state, sid, f"spotify play {uri}", f"Spotify {label}", go, label, "Spotify")


def spotify_exc():
    import spotipy
    return spotipy.SpotifyException


class StationReq(BaseModel):
    guide_id: Optional[str] = None
    url: Optional[str] = None
    name: str
    image: Optional[str] = ""
    category: Optional[str] = "Saved"


class PlayStationReq(BaseModel):
    station_id: Optional[str] = None
    guide_id: Optional[str] = None
    name: Optional[str] = None
    zones: List[str] = []


class PlaySpotifyReq(BaseModel):
    uri: str
    name: Optional[str] = None
    zones: List[str] = []


def _route_zones(state, sid, zones):
    st = _streamer(state, sid)
    src_id = st.get("audio_source")
    src = find(state["audio_sources"], src_id)
    for zid in zones:
        z = find(state["audio_zones"], zid)
        if not z:
            raise HTTPException(400, f"Unknown zone {zid}")
        z.update({"source": src_id, "power": True, "mute": False})
        log_cmd(state, drivers.amp.set_source(z["amp_zone"], amp_input(state, src_id), z["name"], src["name"] if src else src_id, cfg(state, "amp")))


@api_router.get("/tunein/search")
async def tunein_search(q: str):
    try:
        return {"stations": await music.search(q[:80])}
    except httpx_errors() as e:
        raise HTTPException(424, f"TuneIn unavailable: {e}")


@api_router.get("/tunein/browse/{cat}")
async def tunein_browse(cat: str):
    if cat not in music.BROWSE and not re.match(r"^[cg]\d+$", cat):
        raise HTTPException(400, "Unknown category")
    try:
        return await music.browse(cat)
    except httpx_errors() as e:
        raise HTTPException(424, f"TuneIn unavailable: {e}")


def httpx_errors():
    import httpx
    return (httpx.HTTPError, ValueError)


@api_router.get("/tunein/saved")
async def tunein_saved():
    return {"stations": (await get_state()).get("tunein_saved", [])}


@api_router.post("/tunein/saved")
async def tunein_save(req: StationReq):
    if not (req.guide_id or req.url):
        raise HTTPException(400, "guide_id or url required")
    if req.url and not re.match(r"^https?://", req.url):
        raise HTTPException(400, "Stream URL must start with http(s)://")
    state = await get_state()
    sid = req.guide_id or f"url-{uuid.uuid4().hex[:8]}"
    saved = [x for x in state.get("tunein_saved", []) if x["id"] != sid]
    saved.append({"id": sid, "name": req.name[:80], "kind": "tunein" if req.guide_id else "url", "guide_id": req.guide_id,
                  "url": req.url, "image": req.image or "", "category": (req.category or "Saved")[:30]})
    state["tunein_saved"] = saved
    await save_state(state)
    return {"stations": saved}


@api_router.delete("/tunein/saved/{station_id}")
async def tunein_unsave(station_id: str):
    state = await get_state()
    state["tunein_saved"] = [x for x in state.get("tunein_saved", []) if x["id"] != station_id]
    await save_state(state)
    return {"stations": state["tunein_saved"]}


@api_router.post("/stream/{sid}/play_station")
async def stream_station(sid: str, req: PlayStationReq):
    state = await get_state()
    station = find(state.get("tunein_saved", []), req.station_id) if req.station_id else (
        {"id": req.guide_id, "guide_id": req.guide_id, "kind": "tunein", "name": req.name or req.guide_id} if req.guide_id else None)
    entry = await stream_play_station(state, sid, station)
    if entry["status"] == "error":
        await save_state(state)
        raise HTTPException(424, entry["error"])
    _route_zones(state, sid, req.zones)
    await save_state(state)
    return redact_secrets(state)


@api_router.get("/spotify/status")
async def spotify_status():
    conf = (await get_state())["config"].get("spotify") or {}
    tok = await db.spotify.find_one({"key": "token"}, {"_id": 0})
    out = {"configured": bool(conf.get("client_id") and conf.get("client_secret")), "connected": bool(tok),
           "redirect_uri": conf.get("redirect_uri")}
    if tok:
        out.update({"user": tok.get("user"), "premium": tok.get("premium")})
    return out


@api_router.get("/spotify/login")
async def spotify_login():
    conf = (await get_state())["config"].get("spotify") or {}
    if not (conf.get("client_id") and conf.get("client_secret")):
        raise HTTPException(400, "Enter the Spotify Client ID and Secret in Settings first")
    state_tok = _secrets.token_urlsafe(24)
    await db.spotify.replace_one({"key": "oauth_state"}, {"key": "oauth_state", "value": state_tok,
                                 "at": datetime.now(timezone.utc).isoformat()}, upsert=True)
    return {"auth_url": music.oauth(conf, state=state_tok).get_authorize_url()}


@api_router.get("/spotify/callback")
async def spotify_callback(code: str = "", state: str = "", error: str = ""):
    saved = await db.spotify.find_one({"key": "oauth_state"})
    if error or not code or not saved or not _secrets.compare_digest(saved["value"], state):
        return HTMLResponse("<h2>Spotify sign-in failed</h2><p>Start again from the controller's Settings.</p>", status_code=400)
    await db.spotify.delete_one({"key": "oauth_state"})
    conf = (await get_state())["config"].get("spotify") or {}
    try:
        o = music.oauth(conf)
        token = await music.run(lambda: o.get_access_token(code, as_dict=True, check_cache=False))
        sp, token = await music.run(music.client, conf, token)
        me = await music.run(sp.me)
    except Exception as e:
        return HTMLResponse(f"<h2>Spotify sign-in failed</h2><p>{str(e)[:200]}</p>", status_code=400)
    await db.spotify.replace_one({"key": "token"}, {"key": "token", "token": token, "user": me.get("display_name") or me.get("id"),
                                 "premium": me.get("product") == "premium"}, upsert=True)
    return HTMLResponse("<h2>Spotify connected</h2><p>You can close this tab and go back to the controller.</p>")


@api_router.delete("/spotify/link")
async def spotify_unlink():
    await db.spotify.delete_many({})
    return {"ok": True}


@api_router.get("/spotify/library")
async def spotify_library():
    sp = await _spotify_session()
    try:
        return await music.run(music.library, sp)
    except Exception as e:
        raise HTTPException(424, f"Spotify: {str(e)[:200]}")


@api_router.post("/stream/{sid}/play_spotify")
async def stream_spotify(sid: str, req: PlaySpotifyReq):
    if not re.match(r"^spotify:(playlist|album|artist|show):[A-Za-z0-9]+$", req.uri):
        raise HTTPException(400, "Invalid Spotify link")
    state = await get_state()
    entry = await stream_play_spotify(state, sid, req.uri, req.name or req.uri)
    if entry["status"] == "error":
        await save_state(state)
        raise HTTPException(424, entry["error"])
    _route_zones(state, sid, req.zones)
    await save_state(state)
    return redact_secrets(state)


# ---------------------------------------------------------------------------
# Person alerts (UniFi Protect Alarm Manager webhook) + offline alerts
OFFLINE_ALERT_AFTER_S = 180


async def _record_person(state, camera_name, source):
    if not state["camera"].get("armed"):
        log_cmd(state, {"driver": "UniFiProtect", "transport": source, "command": "person detected",
                        "note": f"Person at {camera_name} (ignored — Security disarmed)", "timestamp": drivers._ts(), "status": "simulated"})
        await save_state(state)
        return False
    state["person_alert"] = {"id": uuid.uuid4().hex[:10], "at": datetime.now(timezone.utc).isoformat(),
                             "camera": camera_name, "source": source}
    log_cmd(state, {"driver": "UniFiProtect", "transport": source, "command": "person detected",
                    "note": f"Person at {camera_name}", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return True


@api_router.post("/protect/webhook/{token}")
async def protect_webhook(token: str, request: Request):
    state = await get_state()
    expected = cfg(state, "camera").get("webhook_token") or ""
    if not expected or not _secrets.compare_digest(expected, token):
        raise HTTPException(404, "Not found")
    try:
        body = await request.json()
    except Exception:
        body = {}
    alarm = body.get("alarm") if isinstance(body, dict) else None
    if not isinstance(alarm, dict):
        return {"ok": True, "ignored": True}
    triggers = alarm.get("triggers") or []
    keys = {str(t.get("key", "")).lower() for t in triggers if isinstance(t, dict)}
    if triggers and not keys & {"person", "smartdetectzone", "smart_detect", "motion"}:
        return {"ok": True, "ignored": True}
    shown = await _record_person(state, state["camera"].get("name", "Front Entry"), "Protect webhook")
    return {"ok": True, "alerted": shown}


REBOOT_WINDOW_S = 600  # backend up within 10 min of power-on = the mini-PC itself restarted
REBOOT_BANNER_S = 24 * 3600


def _uptime_s() -> float:
    if sys.platform == "win32":
        import ctypes
        return ctypes.windll.kernel32.GetTickCount64() / 1000
    with open("/proc/uptime") as f:
        return float(f.read().split()[0])


async def record_reboot():
    """Remember when the mini-PC came back after a power cut / Windows restart (not app restarts)."""
    try:
        up = _uptime_s()
    except Exception as e:
        logger.warning("Uptime unavailable: %s", e)
        return
    if up > REBOOT_WINDOW_S:
        return
    now = datetime.now(timezone.utc)
    boot_at = now - timedelta(seconds=up)
    last = await db.meta.find_one({"key": "last_reboot"}, {"_id": 0})
    if last and abs((datetime.fromisoformat(last["boot_at"]) - boot_at).total_seconds()) < 120:
        return  # same boot; backend just restarted itself
    await db.meta.update_one({"key": "last_reboot"}, {"$set": {"boot_at": boot_at.isoformat(), "back_online_at": now.isoformat()}}, upsert=True)


async def recent_reboot():
    r = await db.meta.find_one({"key": "last_reboot"}, {"_id": 0, "key": 0})
    if r and (datetime.now(timezone.utc) - datetime.fromisoformat(r["back_online_at"])).total_seconds() < REBOOT_BANNER_S:
        return r
    return None


@api_router.get("/alerts")
async def alerts():
    doc = await db.system.find_one({"key": STATE_KEY}, {"_id": 0, "person_alert": 1, "offline_alerts": 1, "camera.armed": 1})
    doc = doc or {}
    return {"person_alert": doc.get("person_alert"), "offline_alerts": doc.get("offline_alerts", []),
            "armed": bool((doc.get("camera") or {}).get("armed")), "reboot": await recent_reboot()}


@api_router.post("/protect/test-person")
async def protect_test_person():
    state = await get_state()
    shown = await _record_person(state, state["camera"].get("name", "Front Entry"), "test")
    return {"ok": True, "alerted": shown, "armed": bool(state["camera"].get("armed"))}


@api_router.post("/protect/webhook-token")
async def protect_new_token():
    state = await get_state()
    state["config"]["camera"]["webhook_token"] = _secrets.token_urlsafe(18)
    await save_state(state)
    return {"token": state["config"]["camera"]["webhook_token"]}


async def prune_sessions():
    await db.sessions.delete_many({"expires_at": {"$lt": datetime.now(timezone.utc).isoformat()}})


_offline_since: dict = {}


async def offline_watch():
    try:
        health = await device_health()
    except Exception:
        return
    now = datetime.now(timezone.utc)
    alerts = []
    for d in health["devices"]:
        if d["online"] or not d["live"]:
            _offline_since.pop(d["id"], None)
            continue
        since = _offline_since.setdefault(d["id"], now)
        if (now - since).total_seconds() >= OFFLINE_ALERT_AFTER_S:
            alerts.append({"id": d["id"], "name": d["name"], "ip": d["ip"], "since": since.isoformat()})
    await db.system.update_one({"key": STATE_KEY}, {"$set": {"offline_alerts": alerts}})


class PresetReq(BaseModel):
    name: str
    icon: Optional[str] = "Sparkles"
    actions: List[dict]


def _preset_doc(state, req: PresetReq, pid: str):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "Name is required")
    actions = validate_actions(state, req.actions)
    return {"id": pid, "name": name[:60], "icon": req.icon, "type": "vibrant", "custom": True,
            "desc": f"Preset · {len(actions)} step{'s' if len(actions) != 1 else ''}", "actions": actions}


@api_router.post("/presets")
async def create_preset(req: PresetReq):
    doc = _preset_doc(await get_state(), req, str(uuid.uuid4()))
    await db.scenes.insert_one(copy.deepcopy(doc))
    return doc


@api_router.put("/presets/{preset_id}")
async def update_preset(preset_id: str, req: PresetReq):
    doc = _preset_doc(await get_state(), req, preset_id)
    res = await db.scenes.replace_one({"id": preset_id, "actions": {"$exists": True}}, doc)
    if not res.matched_count:
        raise HTTPException(404, "Preset not found")
    return doc


class ScenePinReq(BaseModel):
    pinned: bool


@api_router.post("/scenes/{scene_id}/pin")
async def pin_scene(scene_id: str, req: ScenePinReq):
    state = await get_state()
    if not (find(state["scenes"], scene_id) or await db.scenes.find_one({"id": scene_id})):
        raise HTTPException(404, "Scene not found")
    pins = [p for p in state.get("pinned_scenes", []) if p != scene_id]
    if req.pinned:
        pins.append(scene_id)
    state["pinned_scenes"] = pins
    await save_state(state)
    return redact_secrets(state)


@api_router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str):
    await db.scenes.delete_one({"id": scene_id})
    state = await get_state()
    if scene_id in state.get("pinned_scenes", []):
        state["pinned_scenes"].remove(scene_id)
        await save_state(state)
    return {"ok": True}


@api_router.post("/settings/audio-follow")
async def set_audio_follow(req: ToggleReq):
    state = await get_state()
    state["audio_follow_tv"] = req.enabled
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/security/arm")
async def set_arm(req: ToggleReq):
    state = await get_state()
    state["camera"]["armed"] = req.enabled
    log_cmd(state, drivers.camera.command(f"arm {req.enabled}", f"Camera {'armed' if req.enabled else 'disarmed'}", cfg(state, "camera")))
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/away")
async def set_away(req: ToggleReq):
    state = await get_state()
    state["away"] = req.enabled
    state["camera"]["armed"] = req.enabled
    if req.enabled:
        apply_scene(state, "all_off")
        state["thermostat"]["mode"] = "auto"
    await save_state(state)
    return redact_secrets(state)


# ---------------------------------------------------------------------------
# Settings / device config
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, updates: dict) -> dict:
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


@api_router.put("/config")
async def update_config(req: ConfigReq):
    state = await get_state()
    merged = state.get("config") or default_config()
    _unmask(req.config, merged)
    _deep_merge(merged, req.config)
    state["config"] = merged
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/config/test/{device}")
async def test_connection(device: str):
    state = await get_state()
    conn = cfg(state, device)
    if not conn.get("live"):
        return {"device": device, "ok": False, "detail": "Device is in demo mode (not live)."}
    try:
        if device == "matrix":
            url = f"http://{conn['host']}:{int(conn.get('port') or 80)}/index.html"
            await asyncio.to_thread(lambda: urllib.request.urlopen(url, timeout=4).close())
            return {"device": device, "ok": True, "detail": f"Matrix web control reachable @ {conn['host']}"}
        elif device == "amp":
            with socket.create_connection((conn["host"], 8080), timeout=4):
                pass
        elif device == "ecobee":
            if not conn.get("paired"):
                raise RuntimeError("Not paired — enter the HomeKit setup code and tap Pair")
            r = await asyncio.to_thread(homekit.thermostat.read)
            return {"device": device, "ok": True, "detail": f"HomeKit OK — {homekit.c_to_f(r.get('current_temp') or 0)}°F, {r.get('humidity')}% RH"}
        elif device == "camera":
            mt = re.match(r"^rtsps?://(?:[^@/]*@)?([^:/]+)(?::(\d+))?", conn.get("rtsp_url") or "")
            if not mt:
                raise RuntimeError("No RTSP/RTSPS link configured")
            with socket.create_connection((mt.group(1), int(mt.group(2) or 554)), timeout=4):
                pass
            return {"device": device, "ok": True, "detail": f"Recorder stream port reachable @ {mt.group(1)}"}
        elif device == "tv":
            sets = [s for s in (conn.get("sets") or {}).values() if s.get("ip")]
            if not sets:
                raise RuntimeError("No TV IP addresses configured")
            with socket.create_connection((sets[0]["ip"], 80), timeout=4):
                pass
        else:
            raise RuntimeError("No test available for this device")
        return {"device": device, "ok": True, "detail": "Reachable"}
    except Exception as e:
        return {"device": device, "ok": False, "detail": str(e)[:200]}


# ---------------------------------------------------------------------------
# Automations
# ---------------------------------------------------------------------------

@api_router.get("/automations")
async def list_automations():
    return await db.automations.find({}, {"_id": 0}).to_list(200)


@api_router.post("/automations")
async def create_automation(auto: Automation):
    doc = auto.model_dump()
    doc["id"] = str(uuid.uuid4())
    await db.automations.insert_one(copy.deepcopy(doc))
    _register_job(doc)
    return doc


@api_router.put("/automations/{auto_id}")
async def update_automation(auto_id: str, auto: Automation):
    doc = auto.model_dump()
    doc["id"] = auto_id
    res = await db.automations.replace_one({"id": auto_id}, copy.deepcopy(doc))
    if res.matched_count == 0:
        raise HTTPException(404, "Automation not found")
    _register_job(doc)
    return doc


@api_router.delete("/automations/{auto_id}")
async def delete_automation(auto_id: str):
    await db.automations.delete_one({"id": auto_id})
    try:
        scheduler.remove_job(auto_id)
    except Exception:
        pass
    return {"ok": True}


@api_router.post("/automations/{auto_id}/run")
async def run_automation(auto_id: str):
    auto = await db.automations.find_one({"id": auto_id}, {"_id": 0})
    if not auto:
        raise HTTPException(404, "Automation not found")
    state = await get_state()
    await apply_scene_any(state, auto["action"]["scene_id"])
    log_cmd(state, {"driver": "Automation", "transport": "manual", "command": auto["action"]["scene_id"],
                    "note": f"Ran '{auto['name']}' manually", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/trigger/{event}")
async def fire_event(event: str):
    state = await get_state()
    if event == "motion":
        state["camera"]["motion"] = True
    autos = await db.automations.find({"enabled": True}, {"_id": 0}).to_list(200)
    fired = []
    for a in autos:
        trig = a.get("trigger", {})
        if trig.get("type") == "event" and trig.get("event") == event:
            await apply_scene_any(state, a["action"]["scene_id"])
            log_cmd(state, {"driver": "Automation", "transport": "event", "command": a["action"]["scene_id"],
                            "note": f"'{a['name']}' triggered by {event}", "timestamp": drivers._ts(), "status": "sent"})
            fired.append(a["name"])
    await save_state(state)
    return {"event": event, "fired": fired, "state": redact_secrets(state)}


# ---------------------------------------------------------------------------
# Camera live stream (UniFi Protect RTSP -> HLS via ffmpeg; demo HLS otherwise)
# ---------------------------------------------------------------------------

@api_router.get("/camera/stream")
async def camera_stream():
    state = await get_state()
    conn = cfg(state, "camera")
    if conn.get("live") and conn.get("rtsp_url") and shutil.which("ffmpeg"):
        _ensure_ffmpeg(conn["rtsp_url"], "cam_front")
        return {"live": True, "hls_url": "/api/camera/hls/cam_front/index.m3u8"}
    return {"live": False, "hls_url": drivers.DEMO_HLS, "demo": True}


@api_router.get("/camera/stream/{cam_id}")
async def camera_stream_one(cam_id: str):
    state = await get_state()
    conn = cfg(state, "camera") if cam_id == "cam_front" else (cfg(state, "cameras").get(cam_id) or {})
    if conn.get("live") and conn.get("rtsp_url") and shutil.which("ffmpeg"):
        _ensure_ffmpeg(conn["rtsp_url"], cam_id)
        return {"live": True, "hls_url": f"/api/camera/hls/{cam_id}/index.m3u8"}
    return {"live": False, "hls_url": drivers.DEMO_HLS, "demo": True}


@api_router.post("/camera/{cam_id}/motion")
async def camera_motion(cam_id: str):
    state = await get_state()
    cam = next((c for c in state["cameras"] if c["id"] == cam_id), None)
    if not cam:
        raise HTTPException(404, "Camera not found")
    cam["motion"] = True
    cam["motion_at"] = datetime.now(timezone.utc).isoformat()
    if cam_id == "cam_front":
        state["camera"]["motion"] = True
    log_cmd(state, drivers.camera.command(f"motion {cam_id}", f"Motion on {cam['name']}", {}))
    clip = {"id": str(uuid.uuid4()), "camera_id": cam_id, "camera_name": cam["name"],
            "ts": datetime.now(timezone.utc).isoformat()}
    await db.clips.insert_one(copy.deepcopy(clip))
    autos = await db.automations.find({"enabled": True}, {"_id": 0}).to_list(200)
    fired = []
    for a in autos:
        trig = a.get("trigger", {})
        if trig.get("type") == "event" and trig.get("event") == "motion":
            await apply_scene_any(state, a["action"]["scene_id"])
            fired.append(a["name"])
    await save_state(state)
    return {"ok": True, "camera": cam_id, "fired": fired, "state": redact_secrets(state)}


@api_router.get("/clips")
async def list_clips():
    clips = await db.clips.find({}, {"_id": 0}).sort("ts", -1).to_list(50)
    return clips


@api_router.delete("/clips")
async def clear_clips():
    await db.clips.delete_many({})
    return {"ok": True}


@api_router.get("/voice/phrases")
async def get_voice_phrases():
    doc = await db.settings.find_one({"key": "voice_phrases"}, {"_id": 0})
    return (doc or {}).get("map", {})


@api_router.put("/voice/phrases")
async def set_voice_phrases(req: dict):
    phrases = req.get("phrases", {})
    await db.settings.update_one({"key": "voice_phrases"}, {"$set": {"map": phrases}}, upsert=True)
    return {"ok": True, "map": phrases}


@api_router.get("/voice/scene/{scene_id}")
async def voice_scene(scene_id: str):
    """Webhook for iOS Shortcuts / Google Assistant routines to run a scene by voice."""
    state = await get_state()
    if not await apply_scene_any(state, scene_id):
        raise HTTPException(404, "Scene not found")
    log_cmd(state, {"driver": "Voice", "transport": "webhook", "command": scene_id,
                    "note": f"Scene '{scene_id}' run by voice", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return {"ok": True, "scene": scene_id}


@api_router.get("/discover")
async def discover(live: bool = False):
    """Suggest device connection info. Real LAN scan only when self-hosted (live=true);
    the cloud demo returns sample results so the wizard flow is usable."""
    demo_devices = {
        "matrix": {"host": JTECH_HOST, "port": 80, "label": f"JTECH-MXT40 (web control) @ {JTECH_HOST}"},
        "amp": {"host": WS66I_HOST, "label": f"WS66i 6-zone @ {WS66I_HOST}"},
        "camera": {"rtsp_url": f"rtsps://{UNIFI_NVR['ip']}:7441/demo-front?enableSrtp", "label": "UniFi G6 PTZ (Front Entry)"},
        "tv": {tid: {"ip": ip, "mac": SONY_TV_MACS[tid]} for tid, ip in SONY_TV_IPS.items()},
    }
    if not live:
        return {"demo": True, "devices": demo_devices}
    # Self-hosted lightweight probe of the known device addresses
    found = {"tv": {}}
    try:
        async def probe(ip, port):
            try:
                fut = asyncio.open_connection(ip, port)
                r, w = await asyncio.wait_for(fut, timeout=0.4)
                w.close()
                return True
            except Exception:
                return False

        matrix_up, tv_up = await asyncio.gather(
            probe(JTECH_HOST, 80), asyncio.gather(*[probe(ip, 80) for ip in SONY_TV_IPS.values()]))
        if matrix_up:
            found["matrix"] = {"host": JTECH_HOST, "port": 80, "label": f"JTECH-MXT40 (web control) @ {JTECH_HOST}"}
        for (disp, ip), ok in zip(SONY_TV_IPS.items(), tv_up):
            if ok:
                found["tv"][disp] = {"ip": ip, "mac": SONY_TV_MACS[disp]}
    except Exception as e:
        return {"demo": True, "error": str(e), "devices": demo_devices}
    return {"demo": False, "devices": found}


async def _tcp_up(host, port, timeout=1.2):
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        _r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        w.close()
        return True, round((loop.time() - t0) * 1000)
    except Exception:
        return False, None


async def _ping_up(host):
    try:
        host = str(ipaddress.ip_address(host))  # only literal IPs reach the ping subprocess
    except ValueError:
        return False, None
    is_win = os.name == "nt"
    args = ["ping", "-n" if is_win else "-c", "1", "-w" if is_win else "-W", "1000" if is_win else "1", host]
    if not shutil.which("ping"):
        return False, None
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        ok = (await asyncio.wait_for(proc.wait(), timeout=3)) == 0
        return ok, round((loop.time() - t0) * 1000) if ok else None
    except Exception:
        return False, None


def _health_targets(state):
    c = state.get("config") or {}
    names = {d["id"]: d["name"] for d in state.get("displays", [])}
    out = []
    for tid, tv in ((c.get("tv") or {}).get("sets") or {}).items():
        if tv.get("ip"):
            out.append({"id": tid, "name": names.get(tid, tid), "kind": "Sony Bravia TV", "ip": tv["ip"], "port": 80,
                        "mac": tv.get("mac", ""), "live": bool((c.get("tv") or {}).get("live"))})
    src_names = {x["id"]: x["name"] for x in state.get("sources", [])}
    for aid, atv in ((c.get("appletv") or {}).get("devices") or {}).items():
        if atv.get("ip"):
            out.append({"id": aid, "name": src_names.get(aid, aid), "kind": "Apple TV 4K", "ip": atv["ip"], "port": 7000,
                        "mac": atv.get("mac", ""), "live": bool((c.get("appletv") or {}).get("live"))})
    ec = c.get("ecobee") or {}
    if ec.get("ip"):
        out.append({"id": "ecobee", "name": "Thermostat", "kind": "Ecobee (HomeKit)", "ip": ec["ip"], "port": None,
                    "mac": ec.get("mac", ""), "live": bool(ec.get("live"))})
    m = c.get("matrix") or {}
    if m.get("host"):
        out.append({"id": "matrix", "name": "HDMI Matrix", "kind": "J-Tech MXT40", "ip": m["host"], "port": int(m.get("port") or 80),
                    "mac": "", "live": bool(m.get("live"))})
    a = c.get("amp") or {}
    if a.get("host"):
        out.append({"id": "amp", "name": "Audio Amp", "kind": "Soundavo WS66i", "ip": a["host"], "port": 8080,
                    "mac": "", "live": bool(a.get("live"))})
    for sid, st in (a.get("streamers") or {}).items():
        if st.get("ip"):
            out.append({"id": sid, "name": st.get("name", sid), "kind": "WS66i streaming module (Arylic/Linkplay)", "ip": st["ip"],
                        "port": 80, "mac": st.get("mac", ""), "live": bool(a.get("live"))})
    nvr = c.get("nvr") or {}
    if nvr.get("ip"):
        out.append({"id": "nvr", "name": "Protect NVR", "kind": "UniFi Network Video Recorder", "ip": nvr["ip"], "port": 7441,
                    "mac": nvr.get("mac", ""), "live": bool((c.get("camera") or {}).get("live"))})
    cam_names = {x["id"]: x["name"] for x in state.get("cameras", [])}
    front = c.get("camera") or {}
    if front.get("ip"):
        out.append({"id": "cam_front", "name": cam_names.get("cam_front", "Front Entry"), "kind": front.get("model", "UniFi Camera"),
                    "ip": front["ip"], "port": None, "mac": front.get("mac", ""), "live": bool(front.get("live"))})
    cams = ([] if front.get("ip") else [("cam_front", front)]) + list((c.get("cameras") or {}).items())
    for cid, cam in cams:
        url = cam.get("rtsp_url") or ""
        mt = re.match(r"^rtsps?://(?:[^@/]*@)?([^:/]+)(?::(\d+))?", url)
        if mt:
            out.append({"id": cid, "name": cam_names.get(cid, cid), "kind": "UniFi Camera (RTSP)", "ip": mt.group(1),
                        "port": int(mt.group(2) or 554), "mac": "", "live": bool(cam.get("live"))})
    # Matrix and Apple TV control were removed from the app.
    return [t for t in out if t["id"] != "matrix" and not t["id"].startswith("atv")]


@api_router.get("/health/devices")
async def device_health():
    state = await get_state()
    targets = _health_targets(state)
    results = await asyncio.gather(*[(_tcp_up(t["ip"], t["port"]) if t["port"] else _ping_up(t["ip"])) for t in targets])
    for t, (ok, ms) in zip(targets, results):
        t.update({"online": ok, "latency_ms": ms, "check": f"TCP {t['port']}" if t["port"] else "ping"})
    arc = await db.meta.find_one({"key": "arc_status"}, {"_id": 0, "key": 0}) or {}
    arc_warnings = [{"tv_id": k, **v} for k, v in arc.items() if not v.get("ok")]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "devices": targets,
            "online": sum(1 for t in targets if t["online"]), "total": len(targets), "arc_warnings": arc_warnings}


# ---------------------------------------------------------------------------
# G6 PTZ — presets/patrol (official API) + experimental continuous move
class PtzGotoReq(BaseModel):
    slot: int


class PtzPatrolReq(BaseModel):
    start: bool
    slot: int = 0


class PtzMoveReq(BaseModel):
    pan: int = 0
    tilt: int = 0
    zoom: int = 0


def _ptz_conn(state):
    return {**cfg(state, "camera"), "nvr_ip": (state["config"].get("nvr") or {}).get("ip", "")}


async def _ptz_run(state, label, payload, coro_fn, quiet=False):
    conn = _ptz_conn(state)
    entry = {"driver": "UniFiPTZ", "transport": "UniFi Protect API", "command": payload, "note": label,
             "timestamp": drivers._ts(), "status": "simulated"}
    if conn.get("live"):
        try:
            await coro_fn(conn)
            entry["status"] = "sent"
        except Exception as e:
            import httpx
            if isinstance(e, (httpx.ConnectError, httpx.TimeoutException)):
                msg = f"Can't reach the Protect recorder at {conn.get('nvr_ip')}"
            elif isinstance(e, httpx.HTTPStatusError):
                msg = f"Protect rejected the request (HTTP {e.response.status_code}) — check the API key / local user"
            else:
                msg = str(e) or type(e).__name__
            entry.update({"status": "error", "error": msg[:200]})
    if not quiet:
        log_cmd(state, entry)
        await save_state(state)
    if entry["status"] == "error":
        raise HTTPException(424, entry["error"])
    return {"ok": True, "status": entry["status"]}


@api_router.get("/ptz/presets")
async def ptz_presets():
    state = await get_state()
    names = [n.strip() for n in (cfg(state, "camera").get("ptz_presets") or "").split(",") if n.strip()]
    return {"presets": [{"slot": -1, "name": "Home"}] + [{"slot": i, "name": n} for i, n in enumerate(names)]}


@api_router.post("/ptz/goto")
async def ptz_goto(req: PtzGotoReq):
    if not -1 <= req.slot <= 9:
        raise HTTPException(400, "slot must be -1..9")
    state = await get_state()
    return await _ptz_run(state, f"PTZ go to preset {req.slot}", f"POST ptz/goto/{req.slot}",
                          lambda c: protect.ptz.goto(c, req.slot))


@api_router.post("/ptz/patrol")
async def ptz_patrol(req: PtzPatrolReq):
    if not 0 <= req.slot <= 4:
        raise HTTPException(400, "slot must be 0..4")
    state = await get_state()
    label = f"PTZ patrol {'start ' + str(req.slot) if req.start else 'stop'}"
    return await _ptz_run(state, label, f"POST ptz/patrol/{'start/' + str(req.slot) if req.start else 'stop'}",
                          lambda c: protect.ptz.patrol(c, req.start, req.slot))


@api_router.post("/ptz/move")
async def ptz_move(req: PtzMoveReq):
    state = await get_state()
    stop = not any((req.pan, req.tilt, req.zoom))
    return await _ptz_run(state, "PTZ stop" if stop else f"PTZ move pan={req.pan} tilt={req.tilt} zoom={req.zoom}",
                          f"POST cameras/<id>/move continuous x={req.pan} y={req.tilt} z={req.zoom}",
                          lambda c: protect.ptz.move(c, req.pan, req.tilt, req.zoom), quiet=not stop)


# ---------------------------------------------------------------------------
# Apple TV in-app pairing (pyatv): companion then airplay
_atv_pairings: dict = {}
_ATV_PROTOS = {"companion": ("credentials", "Companion"), "airplay": ("airplay_credentials", "AirPlay")}


class AtvPairStartReq(BaseModel):
    protocol: str


class AtvPairPinReq(BaseModel):
    protocol: str
    pin: str


@api_router.post("/appletv/{aid}/pair/start")
async def atv_pair_start(aid: str, req: AtvPairStartReq):
    import pyatv
    from pyatv.const import Protocol
    if req.protocol not in _ATV_PROTOS:
        raise HTTPException(400, "protocol must be companion or airplay")
    state = await get_state()
    dev = ((cfg(state, "appletv").get("devices") or {}).get(aid)) or {}
    if not dev.get("ip"):
        raise HTTPException(400, "Set this Apple TV's IP first")
    old = _atv_pairings.pop(aid, None)
    if old:
        await old.close()
    loop = asyncio.get_running_loop()
    found = await pyatv.scan(loop, hosts=[dev["ip"]], timeout=5)
    if not found:
        raise HTTPException(404, f"No Apple TV answered at {dev['ip']} (same network? powered on?)")
    proto = getattr(Protocol, _ATV_PROTOS[req.protocol][1])
    handler = await pyatv.pair(found[0], proto, loop)
    await handler.begin()
    _atv_pairings[aid] = handler
    await db.system.update_one({"key": STATE_KEY}, {"$set": {f"config.appletv.devices.{aid}.id": found[0].identifier or ""}})
    return {"ok": True, "device_provides_pin": handler.device_provides_pin, "name": found[0].name}


@api_router.post("/appletv/{aid}/pair/finish")
async def atv_pair_finish(aid: str, req: AtvPairPinReq):
    handler = _atv_pairings.pop(aid, None)
    if req.protocol not in _ATV_PROTOS:
        raise HTTPException(400, "protocol must be companion or airplay")
    if not handler:
        raise HTTPException(400, "Start pairing first")
    try:
        handler.pin(int(re.sub(r"\D", "", req.pin) or 0))
        await handler.finish()
        if not handler.has_paired:
            raise HTTPException(400, "Pairing failed — check the PIN and try again")
        creds = handler.service.credentials
    finally:
        await handler.close()
    field = _ATV_PROTOS[req.protocol][0]
    state = await get_state()
    state["config"]["appletv"]["devices"].setdefault(aid, {})[field] = creds
    log_cmd(state, {"driver": "AppleTV", "transport": "pyatv pairing", "command": f"pair {req.protocol}",
                    "note": f"Paired {aid} ({req.protocol})", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return redact_secrets(state)


@api_router.post("/camera/snapshot")
async def camera_snapshot():
    state = await get_state()
    log_cmd(state, drivers.camera.snapshot(state["camera"]["name"], cfg(state, "camera")))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


@api_router.get("/camera/hls/{cam_id}/{filename}")
async def camera_hls_cam(cam_id: str, filename: str):
    if not SAFE_SEG.match(cam_id) or not SAFE_SEG.match(filename):
        raise HTTPException(404, "Not found")
    path = (HLS_DIR / cam_id / filename).resolve()
    if not str(path).startswith(str(HLS_DIR.resolve()) + os.sep) or not path.exists():
        raise HTTPException(404, "Segment not ready")
    media = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})


@api_router.get("/camera/hls/{filename}")
async def camera_hls(filename: str):
    if not SAFE_SEG.match(filename):
        raise HTTPException(404, "Not found")
    path = (HLS_DIR / "cam_front" / filename).resolve()
    if not str(path).startswith(str(HLS_DIR.resolve()) + os.sep) or not path.exists():
        raise HTTPException(404, "Segment not ready")
    media = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})


def _ensure_ffmpeg(rtsp_url: str, cam_id: str = "cam_front"):
    if not isinstance(rtsp_url, str) or not rtsp_url.startswith(("rtsp://", "rtsps://")):
        return
    rtsp_url = re.sub(r"[?&]enableSrtp$", "", rtsp_url)  # Protect adds this for SRTP clients; ffmpeg wants plain RTSPS
    proc = _ffmpeg_procs.get(cam_id)
    if proc and proc.poll() is None:
        return
    out = HLS_DIR / cam_id
    out.mkdir(parents=True, exist_ok=True)
    _ffmpeg_procs[cam_id] = subprocess.Popen([
        "ffmpeg", "-protocol_whitelist", "rtsp,rtp,udp,tcp,tls,crypto",
        "-rtsp_transport", "tcp", "-i", rtsp_url,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-f", "hls", "-hls_time", "2", "-hls_list_size", "6",
        "-hls_flags", "delete_segments+append_list",
        str(out / "index.m3u8"),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
app.include_router(api_router)
app.include_router(listen.router)
listen.D.update(db=db, state_key=STATE_KEY, log_limit=LOG_LIMIT)

PUBLIC_EXACT = {"/api", "/api/", "/api/auth/pin", "/api/auth/demo", "/api/bootstrap", "/api/spotify/callback"}
PUBLIC_PREFIXES = ("/api/voice/scene/", "/api/camera/stream", "/api/camera/hls", "/api/protect/webhook/")


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api"):
        return await call_next(request)
    if path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    if not await valid_session(_bearer(request)):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    if request.method not in ("GET", "HEAD") and request.cookies.get(SESSION_COOKIE) and not _origin_ok(request):
        return JSONResponse({"detail": "Cross-site request blocked"}, status_code=403)  # CSRF guard for cookie auth
    return await call_next(request)


ALLOWED_ORIGINS = [o.strip() for o in os.environ["CORS_ORIGINS"].split(",") if o.strip()]
# Any private-LAN / Tailscale origin, so the panel works on whatever network the mini-PC is on.
LAN_ORIGIN_RE = r"^https?://(localhost|127\.0\.0\.1|10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2}|100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])(\.\d{1,3}){2})(:\d+)?$"


def _origin_ok(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0]
    return origin in ALLOWED_ORIGINS or bool(re.match(LAN_ORIGIN_RE, origin)) or urlparse(origin).hostname == host


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=LAN_ORIGIN_RE,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    await get_state()
    await record_reboot()
    await seed_pin()
    await db.sessions.create_index("token")
    if not await db.meta.find_one({"key": "listen_v2_migration"}):
        # Old scenes, presets and schedules are replaced by Shortcuts.
        await db.scenes.delete_many({})
        await db.automations.delete_many({})
        await db.system.update_one({"key": STATE_KEY}, {"$set": {"pinned_scenes": [], "audio_follow_tv": False}})
        await db.meta.insert_one({"key": "listen_v2_migration"})
    await listen.seed_shortcuts()
    await listen.migrate_layout_v2()
    if not scheduler.running:
        scheduler.start()
    scheduler.add_job(offline_watch, "interval", seconds=60, id="offline_watch", replace_existing=True)
    scheduler.add_job(prune_sessions, "interval", hours=6, id="prune_sessions", replace_existing=True)
    await prune_sessions()
    await reload_jobs()
    hk = await db.homekit.find_one({"key": "ecobee"}, {"_id": 0})
    if hk and hk.get("pairing"):
        try:
            await asyncio.to_thread(homekit.thermostat.load, hk["pairing"])
        except Exception as e:
            logger.warning("HomeKit pairing load failed: %s", e)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
