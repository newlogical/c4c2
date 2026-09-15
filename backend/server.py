from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
import copy

import drivers

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Control4-Style Home Controller")
api_router = APIRouter(prefix="/api")

STATE_KEY = "main"
LOG_LIMIT = 40

# ---------------------------------------------------------------------------
# Default apartment configuration (matches the physical rack + wiring)
# ---------------------------------------------------------------------------

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
            "current_temp": 72,
            "humidity": 45,
            "mode": "cool",          # heat | cool | auto | off
            "fan": "auto",            # auto | on | circulate
            "target_heat": 68,
            "target_cool": 74,
            "outdoor_temp": 75,
            "outdoor_condition": "Sunny",
        },
        "camera": {
            "id": "cam_front",
            "name": "Front Entry",
            "online": True,
            "motion": False,
            "resolution": "4K",
        },
        "network": {"unifi_online": True, "matrix_linked": True, "amp_linked": True},
        "scenes": [
            {"id": "all_off", "name": "All Off", "desc": "Power down all TVs & mute every audio zone", "type": "critical", "icon": "Power"},
            {"id": "good_night", "name": "Good Night", "desc": "TVs off, Ecobee to 68° cool, audio muted", "type": "primary", "icon": "Moon"},
            {"id": "movie_night", "name": "Movie Night", "desc": "Apple TV 1 to Living Room TV + audio", "type": "vibrant", "icon": "Clapperboard"},
            {"id": "whole_home_audio", "name": "Whole-Home Audio", "desc": "Sync all 4 audio zones to one source", "type": "vibrant", "icon": "Radio"},
        ],
        "command_log": [],
    }


async def get_state() -> dict:
    doc = await db.system.find_one({"key": STATE_KEY}, {"_id": 0})
    if not doc:
        doc = default_state()
        await db.system.insert_one(copy.deepcopy(doc))
    return doc


async def save_state(state: dict):
    state.pop("_id", None)
    await db.system.replace_one({"key": STATE_KEY}, state, upsert=True)


def log_cmd(state: dict, entry: dict):
    state["command_log"] = ([entry] + state.get("command_log", []))[:LOG_LIMIT]


def find(items, _id):
    return next((i for i in items if i["id"] == _id), None)


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Control4-Style Home Controller API", "demo_mode": drivers.DEMO_MODE}


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
    display = find(state["displays"], req.display_id)
    source = find(state["sources"], req.source_id)
    if not display or not source:
        raise HTTPException(404, "Display or source not found")
    display["source"] = source["id"]
    display["power"] = True
    log_cmd(state, drivers.matrix.route(display["output"], source["input"], display["name"], source["name"]))
    await save_state(state)
    return state


@api_router.post("/matrix/broadcast")
async def matrix_broadcast(req: BroadcastReq):
    state = await get_state()
    source = find(state["sources"], req.source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    for display in state["displays"]:
        display["source"] = source["id"]
        display["power"] = True
        log_cmd(state, drivers.matrix.route(display["output"], source["input"], display["name"], source["name"]))
    await save_state(state)
    return state


@api_router.post("/display/power")
async def display_power(req: DisplayPowerReq):
    state = await get_state()
    display = find(state["displays"], req.display_id)
    if not display:
        raise HTTPException(404, "Display not found")
    display["power"] = req.power
    log_cmd(state, drivers.matrix.command(
        f"CEC {'ON' if req.power else 'STANDBY'} OUT{display['output']:02d}",
        f"{display['name']} power {'ON' if req.power else 'OFF'}"))
    await save_state(state)
    return state


@api_router.post("/display/remote")
async def display_remote(req: RemoteReq):
    state = await get_state()
    source = find(state["sources"], req.source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    log_cmd(state, drivers.appletv.key(source["name"], req.key))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


@api_router.post("/audio/zone")
async def audio_zone(req: ZoneReq):
    state = await get_state()
    zone = find(state["audio_zones"], req.zone_id)
    if not zone:
        raise HTTPException(404, "Zone not found")
    if req.source is not None:
        src = find(state["audio_sources"], req.source)
        zone["source"] = req.source
        zone["power"] = True
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], 1, zone["name"], src["name"] if src else req.source))
    if req.volume is not None:
        zone["volume"] = max(0, min(100, req.volume))
        log_cmd(state, drivers.amp.set_volume(zone["amp_zone"], round(zone["volume"] * 38 / 100), zone["name"], zone["volume"]))
    if req.mute is not None:
        zone["mute"] = req.mute
        log_cmd(state, drivers.amp.set_mute(zone["amp_zone"], req.mute, zone["name"]))
    if req.power is not None:
        zone["power"] = req.power
        log_cmd(state, drivers.amp.set_power(zone["amp_zone"], req.power, zone["name"]))
    await save_state(state)
    return state


@api_router.post("/audio/group")
async def audio_group(req: AudioGroupReq):
    state = await get_state()
    src = find(state["audio_sources"], req.source_id)
    if not src:
        raise HTTPException(404, "Audio source not found")
    vol = max(0, min(100, req.volume))
    for zone in state["audio_zones"]:
        zone["source"] = req.source_id
        zone["volume"] = vol
        zone["mute"] = False
        zone["power"] = True
        log_cmd(state, drivers.amp.set_source(zone["amp_zone"], 1, zone["name"], src["name"]))
        log_cmd(state, drivers.amp.set_volume(zone["amp_zone"], round(vol * 38 / 100), zone["name"], vol))
    await save_state(state)
    return state


@api_router.post("/climate")
async def climate(req: ClimateReq):
    state = await get_state()
    t = state["thermostat"]
    if req.mode is not None:
        t["mode"] = req.mode
        log_cmd(state, drivers.thermostat.set("hvacMode", req.mode))
    if req.fan is not None:
        t["fan"] = req.fan
        log_cmd(state, drivers.thermostat.set("fan", req.fan))
    if req.target_heat is not None:
        t["target_heat"] = max(45, min(90, req.target_heat))
        log_cmd(state, drivers.thermostat.set("heatHoldTemp", t["target_heat"]))
    if req.target_cool is not None:
        t["target_cool"] = max(45, min(95, req.target_cool))
        log_cmd(state, drivers.thermostat.set("coolHoldTemp", t["target_cool"]))
    await save_state(state)
    return state


@api_router.post("/camera/snapshot")
async def camera_snapshot():
    state = await get_state()
    log_cmd(state, drivers.camera.snapshot(state["camera"]["name"]))
    await save_state(state)
    return {"ok": True, "command_log": state["command_log"]}


@api_router.post("/scene/{scene_id}")
async def run_scene(scene_id: str):
    state = await get_state()
    scene = find(state["scenes"], scene_id)
    if not scene:
        raise HTTPException(404, "Scene not found")

    if scene_id == "all_off":
        for d in state["displays"]:
            d["power"] = False
            log_cmd(state, drivers.matrix.command(f"CEC STANDBY OUT{d['output']:02d}", f"{d['name']} OFF"))
        for z in state["audio_zones"]:
            z["mute"] = True
            z["power"] = False
            log_cmd(state, drivers.amp.set_power(z["amp_zone"], False, z["name"]))

    elif scene_id == "good_night":
        for d in state["displays"]:
            d["power"] = False
            log_cmd(state, drivers.matrix.command(f"CEC STANDBY OUT{d['output']:02d}", f"{d['name']} OFF"))
        for z in state["audio_zones"]:
            z["mute"] = True
            log_cmd(state, drivers.amp.set_mute(z["amp_zone"], True, z["name"]))
        state["thermostat"]["mode"] = "cool"
        state["thermostat"]["target_cool"] = 68
        log_cmd(state, drivers.thermostat.set("coolHoldTemp", 68))

    elif scene_id == "movie_night":
        living = find(state["displays"], "tv_living")
        atv = find(state["sources"], "atv1")
        living["source"] = "atv1"
        living["power"] = True
        log_cmd(state, drivers.matrix.route(living["output"], atv["input"], living["name"], atv["name"]))
        az = find(state["audio_zones"], "audio_living")
        az["source"] = "atv1"
        az["power"] = True
        az["mute"] = False
        az["volume"] = 45
        log_cmd(state, drivers.amp.set_source(az["amp_zone"], atv["input"], az["name"], atv["name"]))

    elif scene_id == "whole_home_audio":
        for z in state["audio_zones"]:
            z["source"] = "spotify"
            z["power"] = True
            z["mute"] = False
            z["volume"] = 30
            log_cmd(state, drivers.amp.set_source(z["amp_zone"], 5, z["name"], "Spotify Connect"))

    await save_state(state)
    return state


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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
