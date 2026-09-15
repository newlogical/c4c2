from fastapi import FastAPI, APIRouter, HTTPException
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
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

import drivers

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

scheduler = AsyncIOScheduler()
_ffmpeg_proc = None


# ---------------------------------------------------------------------------
# Default apartment configuration
# ---------------------------------------------------------------------------

def default_config() -> dict:
    return {
        "matrix": {"live": False, "host": "192.168.1.1", "port": 23},
        "amp": {"live": False, "host": "192.168.1.50"},
        "ecobee": {"live": False, "token": "", "thermostat_id": ""},
        "appletv": {"live": False, "devices": {}},
        "camera": {"live": False, "rtsp_url": ""},
    }


def default_state() -> dict:
    return {
        "key": STATE_KEY,
        "pin": "1234",
        "property_name": "Riverside Apartment",
        "sources": [
            {"id": "atv1", "name": "Apple TV 1", "input": 1, "location": "Living Room"},
            {"id": "atv2", "name": "Apple TV 2", "input": 2, "location": "Office"},
            {"id": "atv3", "name": "Apple TV 3", "input": 3, "location": "Master BR"},
            {"id": "atv4", "name": "Apple TV 4", "input": 4, "location": "Guest BR"},
        ],
        "displays": [
            {"id": "tv_living", "name": "Living Room TV", "output": 1, "source": "atv1", "power": True},
            {"id": "tv_office", "name": "Office TV", "output": 2, "source": "atv2", "power": False},
            {"id": "tv_master", "name": "Master Bedroom TV", "output": 3, "source": "atv3", "power": False},
            {"id": "tv_guest", "name": "Guest Bedroom TV", "output": 4, "source": "atv4", "power": False},
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
        "camera": {"id": "cam_front", "name": "Front Entry", "online": True, "motion": False, "resolution": "4K"},
        "network": {"unifi_online": True, "matrix_linked": True, "amp_linked": True},
        "scenes": [
            {"id": "all_off", "name": "All Off", "desc": "Power down all TVs & mute every audio zone", "type": "critical", "icon": "Power"},
            {"id": "good_night", "name": "Good Night", "desc": "TVs off, Ecobee to 68° cool, audio muted", "type": "primary", "icon": "Moon"},
            {"id": "movie_night", "name": "Movie Night", "desc": "Apple TV 1 to Living Room TV + audio", "type": "vibrant", "icon": "Clapperboard"},
            {"id": "whole_home_audio", "name": "Whole-Home Audio", "desc": "Sync all 4 audio zones to one source", "type": "vibrant", "icon": "Radio"},
        ],
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
    return doc


async def save_state(state: dict):
    state.pop("_id", None)
    await db.system.replace_one({"key": STATE_KEY}, state, upsert=True)


def log_cmd(state: dict, entry: dict):
    state["command_log"] = ([entry] + state.get("command_log", []))[:LOG_LIMIT]


def find(items, _id):
    return next((i for i in items if i["id"] == _id), None)


def cfg(state, device):
    return (state.get("config") or {}).get(device, {})


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
        log_cmd(state, drivers.thermostat.set_hold(state["thermostat"]["target_heat"], 68, tc))

    elif scene_id == "movie_night":
        living = find(state["displays"], "tv_living")
        atv = find(state["sources"], "atv1")
        living["source"] = "atv1"
        living["power"] = True
        log_cmd(state, drivers.matrix.route(living["output"], atv["input"], living["name"], atv["name"], mc))
        az = find(state["audio_zones"], "audio_living")
        az.update({"source": "atv1", "power": True, "mute": False, "volume": 45})
        log_cmd(state, drivers.amp.set_source(az["amp_zone"], atv["input"], az["name"], atv["name"], ac))

    elif scene_id == "whole_home_audio":
        for z in state["audio_zones"]:
            z.update({"source": "spotify", "power": True, "mute": False, "volume": 30})
            log_cmd(state, drivers.amp.set_source(z["amp_zone"], 5, z["name"], "Spotify Connect", ac))
    return True


async def run_scene_by_id(scene_id: str, trigger_note: str = ""):
    state = await get_state()
    if apply_scene(state, scene_id):
        if trigger_note:
            log_cmd(state, {"driver": "Automation", "transport": "scheduler", "command": scene_id,
                            "note": trigger_note, "timestamp": drivers._ts(), "status": "sent"})
        await save_state(state)


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


# ---------------------------------------------------------------------------
# Core routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Control4-Style Home Controller API"}


@api_router.post("/auth/pin")
async def verify_pin(req: PinReq):
    state = await get_state()
    return {"success": req.pin == state["pin"]}


@api_router.get("/state")
async def read_state():
    return await get_state()


@api_router.post("/state/reset")
async def reset_state():
    fresh = default_state()
    await save_state(fresh)
    return fresh


@api_router.post("/matrix/route")
async def matrix_route(req: RouteReq):
    state = await get_state()
    display, source = find(state["displays"], req.display_id), find(state["sources"], req.source_id)
    if not display or not source:
        raise HTTPException(404, "Display or source not found")
    display["source"], display["power"] = source["id"], True
    log_cmd(state, drivers.matrix.route(display["output"], source["input"], display["name"], source["name"], cfg(state, "matrix")))
    await save_state(state)
    return state


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
    await save_state(state)
    return state


@api_router.post("/display/power")
async def display_power(req: DisplayPowerReq):
    state = await get_state()
    display = find(state["displays"], req.display_id)
    if not display:
        raise HTTPException(404, "Display not found")
    display["power"] = req.power
    log_cmd(state, drivers.matrix.power(display["output"], req.power, display["name"], cfg(state, "matrix")))
    await save_state(state)
    return state


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
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], 1, zone["name"], src["name"], ac))
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
    return state


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
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], 1, zone["name"], src["name"], ac))
        log_cmd(state, drivers.amp.set_volume(zone["amp_zone"], round(vol * 38 / 100), zone["name"], vol, ac))
    await save_state(state)
    return state


@api_router.post("/climate")
async def climate(req: ClimateReq):
    state = await get_state()
    t, tc = state["thermostat"], cfg(state, "ecobee")
    if req.mode is not None:
        t["mode"] = req.mode
        log_cmd(state, drivers.thermostat.set_mode(req.mode, tc))
    if req.fan is not None:
        t["fan"] = req.fan
        log_cmd(state, drivers.thermostat.set_fan(req.fan, tc))
    if req.target_heat is not None:
        t["target_heat"] = max(45, min(90, req.target_heat))
        log_cmd(state, drivers.thermostat.set_hold(t["target_heat"], t["target_cool"], tc))
    if req.target_cool is not None:
        t["target_cool"] = max(45, min(95, req.target_cool))
        log_cmd(state, drivers.thermostat.set_hold(t["target_heat"], t["target_cool"], tc))
    await save_state(state)
    return state


@api_router.post("/scene/{scene_id}")
async def run_scene(scene_id: str):
    state = await get_state()
    if not apply_scene(state, scene_id):
        raise HTTPException(404, "Scene not found")
    await save_state(state)
    return state


# ---------------------------------------------------------------------------
# Settings / device config
# ---------------------------------------------------------------------------

@api_router.put("/config")
async def update_config(req: ConfigReq):
    state = await get_state()
    merged = state.get("config") or default_config()
    for device, values in req.config.items():
        merged.setdefault(device, {})
        merged[device].update(values)
    state["config"] = merged
    state["network"] = {
        "unifi_online": True,
        "matrix_linked": not merged["matrix"].get("live") or True,
        "amp_linked": not merged["amp"].get("live") or True,
    }
    await save_state(state)
    return state


@api_router.post("/config/test/{device}")
async def test_connection(device: str):
    state = await get_state()
    conn = cfg(state, device)
    if not conn.get("live"):
        return {"device": device, "ok": False, "detail": "Device is in demo mode (not live)."}
    try:
        if device == "matrix":
            import socket
            with socket.create_connection((conn["host"], int(conn.get("port", 23))), timeout=4):
                pass
        elif device == "amp":
            import socket
            with socket.create_connection((conn["host"], 8080), timeout=4):
                pass
        elif device == "ecobee":
            import requests
            r = requests.get("https://api.ecobee.com/1/thermostat?format=json&body=%7B%22selection%22%3A%7B%22selectionType%22%3A%22registered%22%2C%22selectionMatch%22%3A%22%22%7D%7D",
                             headers={"Authorization": f"Bearer {conn.get('token','')}"}, timeout=8)
            r.raise_for_status()
        elif device == "camera":
            if not conn.get("rtsp_url"):
                raise RuntimeError("No RTSP URL configured")
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
    apply_scene(state, auto["action"]["scene_id"])
    log_cmd(state, {"driver": "Automation", "transport": "manual", "command": auto["action"]["scene_id"],
                    "note": f"Ran '{auto['name']}' manually", "timestamp": drivers._ts(), "status": "sent"})
    await save_state(state)
    return state


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
            apply_scene(state, a["action"]["scene_id"])
            log_cmd(state, {"driver": "Automation", "transport": "event", "command": a["action"]["scene_id"],
                            "note": f"'{a['name']}' triggered by {event}", "timestamp": drivers._ts(), "status": "sent"})
            fired.append(a["name"])
    await save_state(state)
    return {"event": event, "fired": fired, "state": state}


# ---------------------------------------------------------------------------
# Camera live stream (UniFi Protect RTSP -> HLS via ffmpeg; demo HLS otherwise)
# ---------------------------------------------------------------------------

@api_router.get("/camera/stream")
async def camera_stream():
    state = await get_state()
    conn = cfg(state, "camera")
    if conn.get("live") and conn.get("rtsp_url") and shutil.which("ffmpeg"):
        _ensure_ffmpeg(conn["rtsp_url"])
        return {"live": True, "hls_url": "/api/camera/hls/index.m3u8"}
    return {"live": False, "hls_url": drivers.DEMO_HLS, "demo": True}


@api_router.post("/camera/snapshot")
async def camera_snapshot():
    state = await get_state()
    log_cmd(state, drivers.camera.snapshot(state["camera"]["name"], cfg(state, "camera")))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


@api_router.get("/camera/hls/{filename}")
async def camera_hls(filename: str):
    path = HLS_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Segment not ready")
    media = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp2t"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "no-cache"})


def _ensure_ffmpeg(rtsp_url: str):
    global _ffmpeg_proc
    HLS_DIR.mkdir(parents=True, exist_ok=True)
    if _ffmpeg_proc and _ffmpeg_proc.poll() is None:
        return
    _ffmpeg_proc = subprocess.Popen([
        "ffmpeg", "-rtsp_transport", "tcp", "-i", rtsp_url,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-f", "hls", "-hls_time", "2", "-hls_list_size", "6",
        "-hls_flags", "delete_segments+append_list",
        str(HLS_DIR / "index.m3u8"),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------------------
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def on_startup():
    await get_state()
    if not scheduler.running:
        scheduler.start()
    await reload_jobs()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
