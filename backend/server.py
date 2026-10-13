from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import logging
import copy
import uuid
import shutil
import subprocess
import asyncio
import socket
import secrets
import re
import bcrypt
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

import drivers
import homekit

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
        "matrix": {"live": False, "host": "192.168.1.1", "port": 23},
        "amp": {"live": False, "host": "192.168.1.50", "input_map": {
            "atv1": 1, "atv2": 2, "atv3": 3, "atv4": 4,
            "spotify": 5, "airplay": 6, "tv_audio": 6,
        }},
        "ecobee": {"live": False, "paired": False, **ECOBEE_LAN},
        "appletv": {"live": False, "devices": {}},
        "camera": {"live": False, "rtsp_url": ""},
        "cameras": {
            "cam_living": {"live": False, "rtsp_url": ""},
            "cam_back": {"live": False, "rtsp_url": ""},
            "cam_garage": {"live": False, "rtsp_url": ""},
        },
        "tv": {"live": False, "sets": {
            tid: {"ip": ip, "mac": SONY_TV_MACS[tid], "hdmi_input": 1, "psk": ""} for tid, ip in SONY_TV_IPS.items()
        }},
        "setup_done": False,
    }


def default_state() -> dict:
    return {
        "key": STATE_KEY,
        "property_name": "Riverside Apartment",
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
            {"id": "atv3", "name": "Apple TV 3"},
            {"id": "atv4", "name": "Apple TV 4"},
            {"id": "spotify", "name": "Spotify Connect"},
            {"id": "airplay", "name": "AirPlay 2"},
            {"id": "tv_audio", "name": "TV Audio"},
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
            {"id": "cam_living", "name": "Living Room", "online": True, "motion": False},
            {"id": "cam_back", "name": "Backyard", "online": True, "motion": False},
            {"id": "cam_garage", "name": "Garage", "online": True, "motion": False},
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
            {"id": "cam_living", "name": "Living Room", "online": True, "motion": False},
            {"id": "cam_back", "name": "Backyard", "online": True, "motion": False},
            {"id": "cam_garage", "name": "Garage", "online": True, "motion": False},
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


def _bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return auth[7:] if auth.startswith("Bearer ") else ""


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


async def apply_scene_any(state: dict, scene_id: str) -> bool:
    if apply_scene(state, scene_id):
        return True
    doc = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    if not doc:
        return False
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
async def verify_pin(req: PinReq):
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
        token = await create_session()
        return {"success": True, "token": token}
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
async def change_pin(req: ChangePinReq):
    doc = await db.auth.find_one({"key": "pin"})
    if not doc or not verify_pin_hash(req.current, doc["pin_hash"]):
        raise HTTPException(400, "Current PIN is incorrect")
    if not (req.new_pin.isdigit() and len(req.new_pin) == 4):
        raise HTTPException(400, "New PIN must be exactly 4 digits")
    await db.auth.update_one({"key": "pin"}, {"$set": {"pin_hash": hash_pin(req.new_pin), "fails": 0}, "$unset": {"locked_until": ""}})
    return {"success": True}


@api_router.post("/auth/demo")
async def demo_login():
    state = await get_state()
    if not is_demo_mode(state):
        raise HTTPException(403, "Demo bypass is disabled once real devices are configured")
    token = await create_session()
    return {"success": True, "token": token}


@api_router.post("/auth/logout")
async def logout(request: Request):
    token = _bearer(request)
    if token:
        await db.sessions.delete_one({"token": token})
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
    log_cmd(state, drivers.matrix.power(display["output"], req.power, display["name"], cfg(state, "matrix")))
    log_cmd(state, await asyncio.to_thread(drivers.tv.power, display["name"], req.power, tv_conn(state, display["id"]), True))
    if req.power:
        link_zone_to_display(state, display)
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


@api_router.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str):
    await db.scenes.delete_one({"id": scene_id})
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
            with socket.create_connection((conn["host"], int(conn.get("port", 23))), timeout=4):
                pass
        elif device == "amp":
            with socket.create_connection((conn["host"], 8080), timeout=4):
                pass
        elif device == "ecobee":
            if not conn.get("paired"):
                raise RuntimeError("Not paired — enter the HomeKit setup code and tap Pair")
            r = await asyncio.to_thread(homekit.thermostat.read)
            return {"device": device, "ok": True, "detail": f"HomeKit OK — {homekit.c_to_f(r.get('current_temp') or 0)}°F, {r.get('humidity')}% RH"}
        elif device == "camera":
            if not conn.get("rtsp_url"):
                raise RuntimeError("No RTSP URL configured")
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
        "matrix": {"host": "192.168.1.20", "port": 23, "label": "JTECH-MXT40 (Telnet) @ 192.168.1.20"},
        "amp": {"host": "192.168.1.35", "label": "WS66i 6-zone @ 192.168.1.35"},
        "camera": {"rtsp_url": "rtsp://192.168.1.2:7447/2b9f1c-front", "label": "UniFi Front Entry"},
        "tv": {tid: {"ip": ip, "mac": SONY_TV_MACS[tid]} for tid, ip in SONY_TV_IPS.items()},
    }
    if not live:
        return {"demo": True, "devices": demo_devices}
    # Self-hosted lightweight scan of the local /24 for known ports (bounded)
    found = {"tv": {}}
    try:
        host_ip = socket.gethostbyname(socket.gethostname())
        base = ".".join(host_ip.split(".")[:3])

        async def probe(ip, port):
            try:
                fut = asyncio.open_connection(ip, port)
                r, w = await asyncio.wait_for(fut, timeout=0.4)
                w.close()
                return True
            except Exception:
                return False

        async def scan(port):
            hits = await asyncio.gather(*[probe(f"{base}.{h}", port) for h in range(1, 255)])
            return [f"{base}.{h}" for h, ok in zip(range(1, 255), hits) if ok]

        matrix_hosts, tv_up = await asyncio.gather(
            scan(23), asyncio.gather(*[probe(ip, 80) for ip in SONY_TV_IPS.values()]))
        if matrix_hosts:
            found["matrix"] = {"host": matrix_hosts[0], "port": 23, "label": f"Telnet device @ {matrix_hosts[0]}"}
        for (disp, ip), ok in zip(SONY_TV_IPS.items(), tv_up):
            if ok:
                found["tv"][disp] = {"ip": ip, "mac": SONY_TV_MACS[disp]}
    except Exception as e:
        return {"demo": True, "error": str(e), "devices": demo_devices}
    return {"demo": False, "devices": found}


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
    if not isinstance(rtsp_url, str) or not rtsp_url.startswith("rtsp://"):
        return
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

PUBLIC_EXACT = {"/api", "/api/", "/api/auth/pin", "/api/auth/demo", "/api/bootstrap"}
PUBLIC_PREFIXES = ("/api/voice/scene/", "/api/camera/stream", "/api/camera/hls")


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api"):
        return await call_next(request)
    if path in PUBLIC_EXACT or path.startswith(PUBLIC_PREFIXES):
        return await call_next(request)
    if not await valid_session(_bearer(request)):
        return JSONResponse({"detail": "Not authenticated"}, status_code=401)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    await get_state()
    await seed_pin()
    await db.sessions.create_index("token")
    if not scheduler.running:
        scheduler.start()
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
