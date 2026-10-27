"""Room-based WS66i audio: rooms, Party Mode, Restore Default Audio and Shortcuts.

All amp writes go through one lock + one Telnet session per batch and are confirmed
by reading the zone status back. In LIVE mode a failed/unconfirmed command raises
424 and the stored state is not changed for that zone.
"""
import asyncio
import copy
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import drivers
import linkplay

router = APIRouter(prefix="/api")
D = {}  # injected by server: db, state_key, log_limit
_amp_lock = asyncio.Lock()
DOC = {"key": "main"}
SYNC_EVERY_S = 5

DEFAULT_ROOMS = [
    {"id": "living", "name": "Living Room", "amp_zone": 1, "visible": True, "default_input": 1, "max_volume": 100, "tv_id": "tv_living",
     "sources": [{"input": 1, "label": "TV"}, {"input": 3, "label": "Mobile Device"}]},
    {"id": "office", "name": "Office", "amp_zone": 2, "visible": True, "default_input": 5, "max_volume": 100, "tv_id": "tv_office",
     "sources": [{"input": 5, "label": "TV", "wiim": "wiim1", "wiim_mode": "bluetooth"},
                 {"input": 5, "label": "Mobile Device", "wiim": "wiim1", "wiim_mode": "wifi"}]},
    {"id": "master", "name": "Master Bedroom", "amp_zone": 3, "visible": True, "default_input": 2, "max_volume": 100, "tv_id": "tv_master",
     "sources": [{"input": 2, "label": "TV"}, {"input": 4, "label": "Mobile Device"}]},
    {"id": "bathroom", "name": "Bathroom", "amp_zone": 4, "visible": True, "default_input": 6, "max_volume": 100, "tv_id": None,
     "sources": [{"input": 6, "label": "Mobile Device", "wiim": "wiim2", "wiim_mode": "wifi"}, {"input": 1, "label": "Living Room TV"},
                 {"input": 5, "label": "Office TV"}, {"input": 2, "label": "Master Bedroom TV"}]},
    {"id": "zone5", "name": "Zone 5", "amp_zone": 5, "visible": False, "default_input": 1, "max_volume": 100, "tv_id": None, "sources": []},
    {"id": "zone6", "name": "Zone 6", "amp_zone": 6, "visible": False, "default_input": 1, "max_volume": 100, "tv_id": None, "sources": []},
]
DEFAULT_PARTY_SOURCES = [{"input": 3, "label": "Mobile Device from Living Room"}, {"input": 1, "label": "Living Room TV"},
                         {"input": 5, "label": "Office TV", "wiim": "wiim1", "wiim_mode": "bluetooth"},
                         {"input": 2, "label": "Master Bedroom TV"}]
# Layout shipped before the WiiMs were installed; migrate_layout_v2 only replaces parts still equal to this.
_V1 = {"office": [{"input": 5, "label": "TV"}, {"input": 6, "label": "Mobile Device"}],
       "bathroom": [{"input": 6, "label": "Mobile Device"}, {"input": 1, "label": "Living Room TV"},
                    {"input": 5, "label": "Office TV"}, {"input": 2, "label": "Master Bedroom TV"}],
       "party": [{"input": 6, "label": "Mobile Device from Living Room"}, {"input": 1, "label": "Living Room TV"},
                 {"input": 5, "label": "Office TV"}, {"input": 2, "label": "Master Bedroom TV"}]}
FOUR = ["living", "office", "master", "bathroom"]
# Amp inputs fed by a Sony TV over HDMI ARC. Picking one makes sure that TV's sound output is "Audio System".
# Office TV is left out on purpose: its sound goes to the Office WiiM over Bluetooth.
DEFAULT_ARC_INPUTS = {"1": "tv_living", "2": "tv_master"}
ARC_TRIES = 4

DEFAULT_WIIMS = [{"id": "wiim1", "name": "Office WiiM", "ip": "", "amp_input": 5},
                 {"id": "wiim2", "name": "Bathroom WiiM", "ip": "", "amp_input": 6}]
WIIM_MODES = {"wifi": "Wi-Fi / AirPlay", "bluetooth": "Bluetooth", "line-in": "Line in", "optical": "Optical"}
# LinkPlay getPlayerStatus "mode" codes for the non-network inputs
_WIIM_MODE_CODE = {"line-in": "40", "bluetooth": "41", "optical": "43"}
DEFAULT_SHORTCUTS = [
    {"name": "Watch TV", "icon": "Tv", "description": "Every room back to its TV sound; Bathroom on Mobile Device",
     "rooms": {"living": {"input": 1}, "office": {"input": 5}, "master": {"input": 2}, "bathroom": {"input": 6}}},
    {"name": "Music Everywhere", "icon": "PartyPopper", "description": "Party Mode: Mobile Device in all four rooms",
     "rooms": {}, "party": {"enabled": True, "input": 3, "rooms": FOUR}},
    {"name": "Bathroom TV Audio", "icon": "Bath", "description": "Bathroom plays the Living Room TV",
     "rooms": {"bathroom": {"input": 1}}},
    {"name": "Good Night", "icon": "Moon", "description": "Turn off all four speaker zones",
     "rooms": {r: {"power": False} for r in FOUR}},
    {"name": "Restore Defaults", "icon": "RotateCcw", "description": "Default source in every room", "rooms": {}, "restore_defaults": True},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


class AmpError(Exception):
    pass


# ---------------------------------------------------------------------------
# storage
async def load() -> dict:
    doc = await D["db"].listen.find_one(DOC, {"_id": 0})
    if not doc:
        doc = {**DOC, "rooms": copy.deepcopy(DEFAULT_ROOMS), "party_sources": copy.deepcopy(DEFAULT_PARTY_SOURCES),
               "status": {}, "party": {"active": False, "input": 3, "rooms": list(FOUR), "saved": {}}}
        await D["db"].listen.insert_one(copy.deepcopy(doc))
    st = await D["db"].system.find_one({"key": D["state_key"]}, {"_id": 0, "config.amp": 1}) or {}
    doc["_amp"] = (st.get("config") or {}).get("amp") or {}
    doc.setdefault("wiims", copy.deepcopy(DEFAULT_WIIMS))
    doc.setdefault("arc_inputs", dict(DEFAULT_ARC_INPUTS))
    for r in doc["rooms"]:
        doc["status"].setdefault(r["id"], {"power": False, "input": r["default_input"], "volume": 30, "mute": False})
    return doc


async def store(doc: dict):
    await D["db"].listen.update_one(DOC, {"$set": {k: v for k, v in doc.items() if k not in ("key", "_amp")}}, upsert=True)


def room(doc, rid) -> dict:
    r = next((x for x in doc["rooms"] if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, "Room not found")
    return r


def live(doc) -> bool:
    return bool(doc["_amp"].get("live"))


async def log(entries: List[dict]):
    if entries:
        await D["db"].system.update_one({"key": D["state_key"]}, {"$push": {"command_log": {
            "$each": entries, "$position": 0, "$slice": D["log_limit"]}}})


def _entry(cmd, note, status, error=None):
    e = {"driver": "WS66i", "transport": "Telnet TCP 8080 (pyws66i)", "command": cmd, "note": note,
         "timestamp": _now(), "status": status}
    if error:
        e["error"] = error
    return e


# ---------------------------------------------------------------------------
# amplifier I/O
def _pct_to_amp(p):
    return round(max(0, min(100, p)) * 38 / 100)


def _amp_to_pct(v):
    return round(v * 100 / 38)


def _status_dict(st):
    return {"power": st.power, "input": st.source, "volume": _amp_to_pct(st.volume), "mute": st.mute}


def _run_batch(host, ops, read_only_zones):
    """Blocking: one session; apply ops [(zone, changes)], then read each zone back."""
    from pyws66i import get_ws66i
    amp = get_ws66i(host)
    try:
        amp.open()
    except Exception as e:
        raise AmpError(f"Can't connect to the amplifier at {host} ({e.__class__.__name__}: {e})")
    try:
        out = {}
        for zone, ch in ops:
            z = 10 + zone
            if ch.get("power") is True:
                amp.set_power(z, True)
            if ch.get("input") is not None:
                amp.set_source(z, ch["input"])
            if ch.get("volume") is not None:
                amp.set_volume(z, _pct_to_amp(ch["volume"]))
            if ch.get("mute") is not None:
                amp.set_mute(z, ch["mute"])
            if ch.get("power") is False:
                amp.set_power(z, False)
        for zone in {z for z, _ in ops} | set(read_only_zones):
            st = amp.zone_status(10 + zone)
            out[zone] = _status_dict(st) if st else None
        return out
    finally:
        try:
            amp.close()
        except Exception:
            pass


def _mismatch(ch, got):
    bad = []
    if ch.get("power") is not None and got["power"] != ch["power"]:
        bad.append("power")
    if got["power"]:  # an amp zone that is off may not report source/volume changes
        if ch.get("input") is not None and got["input"] != ch["input"]:
            bad.append("source")
        if ch.get("volume") is not None and abs(got["volume"] - ch["volume"]) > 3:
            bad.append("volume")
        if ch.get("mute") is not None and got["mute"] != ch["mute"]:
            bad.append("mute")
    return bad


def _describe(r, ch):
    parts = []
    if ch.get("power") is not None:
        parts.append(f"power {'on' if ch['power'] else 'off'}")
    if ch.get("input") is not None:
        parts.append(f"source {ch['input']}")
    if ch.get("volume") is not None:
        parts.append(f"volume {ch['volume']}%")
    if ch.get("mute") is not None:
        parts.append("mute" if ch["mute"] else "unmute")
    return f"{r['name']}: " + ", ".join(parts)


def _cmd(r, ch):
    z = 10 + r["amp_zone"]
    c = []
    if ch.get("power") is not None:
        c.append(f"<{z}PR{'01' if ch['power'] else '00'}")
    if ch.get("input") is not None:
        c.append(f"<{z}CH{ch['input']:02d}")
    if ch.get("volume") is not None:
        c.append(f"<{z}VO{_pct_to_amp(ch['volume']):02d}")
    if ch.get("mute") is not None:
        c.append(f"<{z}MU{'01' if ch['mute'] else '00'}")
    return " ".join(c)


def find_source(r, label=None, inp=None):
    srcs = r.get("sources") or []
    if label is not None:
        return next((x for x in srcs if x["label"] == label), None)
    return next((x for x in srcs if x["input"] == inp), None)


async def wiim_switch(doc, src):
    """Put the WiiM a source relies on into the right mode (e.g. Bluetooth for TV sound) and confirm it."""
    if not src or not src.get("wiim") or not src.get("wiim_mode"):
        return
    w = next((x for x in doc["wiims"] if x["id"] == src["wiim"]), None)
    mode = src["wiim_mode"]
    name = (w or {}).get("name") or src["wiim"]
    entry = {"driver": "WiiM", "transport": "LinkPlay HTTP API", "command": f"setPlayerCmd:switchmode:{mode}",
             "note": f"{name} → {WIIM_MODES.get(mode, mode)} ({src['label']})", "timestamp": _now()}
    if not live(doc):
        await log([{**entry, "status": "simulated"}])
        return
    if not w or not w.get("ip"):
        await log([{**entry, "status": "error", "error": "no IP address set"}])
        raise HTTPException(424, f"{name} has no IP address yet — set it in Settings → Rooms & sources")
    try:
        await linkplay.switch_mode(w["ip"], mode)
        code = None
        for _ in range(6):  # the WiiM takes a moment to change input
            await asyncio.sleep(0.5)
            code = str((await linkplay.status(w["ip"])).get("mode"))
            if (code == _WIIM_MODE_CODE[mode]) if mode in _WIIM_MODE_CODE else (code not in _WIIM_MODE_CODE.values()):
                break
        else:
            raise RuntimeError(f"still reports mode {code}")
    except Exception as e:
        await log([{**entry, "status": "error", "error": str(e)}])
        raise HTTPException(424, f"{name} did not switch to {WIIM_MODES.get(mode, mode)}: {e}")
    await log([{**entry, "status": "confirmed"}])


async def _tv(tv_id):
    st = await D["db"].system.find_one({"key": D["state_key"]}, {"_id": 0, "config.tv": 1, "displays": 1}) or {}
    t = (st.get("config") or {}).get("tv") or {}
    name = next((d["name"] for d in st.get("displays") or [] if d["id"] == tv_id), tv_id)
    return {**((t.get("sets") or {}).get(tv_id) or {}), "live": bool(t.get("live"))}, name


async def ensure_arc(tv_id):
    """Check the TV's sound output and switch it to Audio System (ARC). Failures only warn (Device Health)."""
    conn, name = await _tv(tv_id)
    entry = {"driver": "SonyBravia", "transport": "Bravia REST (audio 1.1)", "command": "setSoundSettings outputTerminal=audioSystem",
             "note": f"{name}: sound output → Audio System (ARC)", "timestamp": _now()}
    if not conn["live"]:
        await log([{**entry, "status": "simulated"}])
        result = {"ok": True, "simulated": True}
    else:
        result, err = None, None
        for i in range(ARC_TRIES):  # a TV that was just woken needs a few seconds before it answers
            try:
                before = await asyncio.to_thread(drivers.tv.get_output, conn)
                if before != "audioSystem":
                    await asyncio.to_thread(drivers.tv.set_output, conn)
                    await asyncio.sleep(1)
                    after = await asyncio.to_thread(drivers.tv.get_output, conn)
                    if after != "audioSystem":
                        raise RuntimeError(f"TV still reports sound output '{after}'")
                result = {"ok": True, "was": before}
                break
            except Exception as e:
                err = str(e)[:200]
                if i < ARC_TRIES - 1:
                    await asyncio.sleep(4)
        if result is None:
            result = {"ok": False, "error": err}
        await log([{**entry, "status": "confirmed" if result["ok"] else "error", **({"error": result["error"]} if not result["ok"] else {})}])
    await D["db"].meta.update_one({"key": "arc_status"}, {"$set": {tv_id: {**result, "name": name, "at": _now()}}}, upsert=True)


_arc_tasks: Dict[str, asyncio.Task] = {}


async def prepare_source(doc, src, wiim=True):
    """Everything a source needs before the amp switches to it: WiiM mode, and ARC on the TV that feeds it."""
    if not src:
        return
    if wiim:
        await wiim_switch(doc, src)
    tv_id = doc["arc_inputs"].get(str(src["input"]))
    if tv_id and not (_arc_tasks.get(tv_id) and not _arc_tasks[tv_id].done()):
        _arc_tasks[tv_id] = asyncio.create_task(ensure_arc(tv_id))  # background: never delays or blocks the room


async def apply(doc, changes: Dict[str, dict]):
    """changes: {room_id: {power?, input?, volume?, mute?}}. Updates doc['status'] only for confirmed zones."""
    changes = {rid: {k: v for k, v in ch.items() if v is not None and k != "label"} for rid, ch in changes.items()}
    changes = {rid: ch for rid, ch in changes.items() if ch}
    if not changes:
        return
    rooms = {rid: room(doc, rid) for rid in changes}
    for rid, ch in changes.items():
        if "volume" in ch:
            ch["volume"] = max(0, min(int(rooms[rid].get("max_volume", 100)), int(ch["volume"])))
    if not live(doc):
        for rid, ch in changes.items():
            doc["status"][rid].update(ch)
        await log([_entry(_cmd(rooms[r], ch), _describe(rooms[r], ch), "simulated") for r, ch in changes.items()])
        return
    host = doc["_amp"].get("host")
    async with _amp_lock:
        try:
            got = await asyncio.to_thread(_run_batch, host, [(rooms[r]["amp_zone"], ch) for r, ch in changes.items()], [])
        except AmpError as e:
            await log([_entry(_cmd(rooms[r], ch), _describe(rooms[r], ch), "error", str(e)) for r, ch in changes.items()])
            raise HTTPException(424, str(e))
    errors, entries = [], []
    for rid, ch in changes.items():
        st = got.get(rooms[rid]["amp_zone"])
        if st is None:
            errors.append(f"{rooms[rid]['name']}: no response from the amplifier")
            entries.append(_entry(_cmd(rooms[rid], ch), _describe(rooms[rid], ch), "error", "no status reply"))
            continue
        doc["status"][rid].update(st)
        bad = _mismatch(ch, st)
        if bad:
            errors.append(f"{rooms[rid]['name']}: amplifier did not confirm {', '.join(bad)}")
            entries.append(_entry(_cmd(rooms[rid], ch), _describe(rooms[rid], ch), "error", f"unconfirmed: {bad}"))
        else:
            entries.append(_entry(_cmd(rooms[rid], ch), _describe(rooms[rid], ch), "confirmed"))
    await log(entries)
    doc["synced_at"] = _now()
    if errors:
        await store(doc)
        raise HTTPException(424, "; ".join(errors))


async def sync(doc, force=False):
    if not live(doc):
        return
    last = doc.get("synced_at")
    if not force and last and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() < SYNC_EVERY_S:
        return
    vis = [r for r in doc["rooms"] if r.get("visible")]
    async with _amp_lock:
        try:
            got = await asyncio.to_thread(_run_batch, doc["_amp"].get("host"), [], [r["amp_zone"] for r in vis])
        except AmpError as e:
            doc["amp_error"] = str(e)
            return
    missing = [r["name"] for r in vis if got.get(r["amp_zone"]) is None]
    for r in vis:
        if got.get(r["amp_zone"]):
            doc["status"][r["id"]].update(got[r["amp_zone"]])
    doc["amp_error"] = f"No status reply for: {', '.join(missing)}" if missing else None
    doc["synced_at"] = _now()
    await store(doc)


def view(doc):
    party = doc["party"]
    return {"live": live(doc), "synced_at": doc.get("synced_at"), "amp_error": doc.get("amp_error") if live(doc) else None,
            "rooms": [{**r, "status": doc["status"][r["id"]], "in_party": party["active"] and r["id"] in party["rooms"]}
                      for r in doc["rooms"]],
            "party_sources": doc["party_sources"], "wiims": doc["wiims"], "wiim_modes": WIIM_MODES,
            "party": {k: party[k] for k in ("active", "input", "rooms")}}


# ---------------------------------------------------------------------------
# party / defaults engine
def _snap(doc, rid):
    s = doc["status"][rid]
    return {k: s[k] for k in ("power", "input", "volume", "mute")}


def _close_party_if_empty(doc, keep_rooms):
    p = doc["party"]
    if p["active"] and not p["rooms"]:  # everyone left: end the party but remember who usually joins
        p["active"], p["saved"], p["rooms"] = False, {}, keep_rooms


async def party_on(doc, inp=None, rooms=None):
    p = doc["party"]
    if inp is not None:
        if inp not in [s["input"] for s in doc["party_sources"]]:
            raise HTTPException(400, "Not a Party Mode source")
        p["input"] = inp
    if rooms is not None:
        if p["active"]:
            for rid in [r for r in p["rooms"] if r not in rooms]:
                await party_leave(doc, rid)
        p["rooms"] = [r for r in rooms if any(x["id"] == r for x in doc["rooms"])]
    await sync(doc, force=True)  # snapshot what the amp really has
    for rid in p["rooms"]:
        p["saved"].setdefault(rid, _snap(doc, rid))
    p["active"] = True
    if p["rooms"]:
        await prepare_source(doc, next((x for x in doc["party_sources"] if x["input"] == p["input"]), None))
    await apply(doc, {rid: {"power": True, "input": p["input"]} for rid in p["rooms"]})


async def party_off(doc, restore=True):
    p = doc["party"]
    saved, p["active"], p["saved"] = p["saved"], False, {}
    if restore:
        await apply(doc, {rid: s for rid, s in saved.items()})


async def party_join(doc, rid):
    p = doc["party"]
    room(doc, rid)
    if rid not in p["rooms"]:
        p["rooms"].append(rid)
    if p["active"]:
        await sync(doc, force=True)
        p["saved"].setdefault(rid, _snap(doc, rid))
        await apply(doc, {rid: {"power": True, "input": p["input"]}})


async def party_leave(doc, rid, restore=True):
    p = doc["party"]
    p["rooms"] = [r for r in p["rooms"] if r != rid]
    saved = p["saved"].pop(rid, None)
    if p["active"] and saved and restore:
        await apply(doc, {rid: saved})


async def restore_defaults(doc):
    if doc["party"]["active"]:
        await party_off(doc, restore=False)
    for inp in {r["default_input"] for r in doc["rooms"] if r.get("visible")}:
        await prepare_source(doc, {"input": inp}, wiim=False)
    await apply(doc, {r["id"]: {"input": r["default_input"]} for r in doc["rooms"] if r.get("visible")})


async def run_shortcut(doc, sc):
    keep = list(doc["party"]["rooms"])
    if sc.get("restore_defaults"):
        await restore_defaults(doc)
    party = sc.get("party") or None
    if party:
        if party.get("enabled"):
            await party_on(doc, party.get("input"), party.get("rooms"))
        elif doc["party"]["active"]:
            await party_off(doc)
    changes = {}
    for rid, ch in (sc.get("rooms") or {}).items():
        r = next((x for x in doc["rooms"] if x["id"] == rid), None)
        src = find_source(r, ch.get("label"), ch.get("input")) if r and (ch.get("label") or ch.get("input")) else None
        ch = {k: ch.get(k) for k in ("power", "input", "volume", "mute") if ch.get(k) is not None}
        if r and "input" in ch and not src:
            ch.pop("input")  # that source was removed from the room since the shortcut was saved
        if not ch or not r:
            continue
        if src:
            ch["input"] = src["input"]
            await prepare_source(doc, src)
            doc["status"][rid]["source_label"] = src["label"]
        if doc["party"]["active"] and rid in doc["party"]["rooms"] and ("input" in ch or "power" in ch):
            await party_leave(doc, rid, restore=False)
        changes[rid] = ch
    _close_party_if_empty(doc, keep)
    await apply(doc, changes)


# ---------------------------------------------------------------------------
# API
class RoomReq(BaseModel):
    power: Optional[bool] = None
    input: Optional[int] = None
    label: Optional[str] = None
    volume: Optional[int] = None
    mute: Optional[bool] = None


class PartyReq(BaseModel):
    active: bool


class PartySourceReq(BaseModel):
    input: int


class PartyRoomReq(BaseModel):
    join: bool


class PartyMasterReq(BaseModel):
    delta: int


class SourceItem(BaseModel):
    input: int = Field(ge=1, le=6)
    label: str
    wiim: Optional[str] = None
    wiim_mode: Optional[Literal["wifi", "bluetooth", "line-in", "optical"]] = None


class WiimItem(BaseModel):
    id: str
    name: str
    ip: str = ""
    amp_input: Optional[int] = Field(None, ge=1, le=6)


class RoomLayout(BaseModel):
    id: str
    name: str
    amp_zone: int = Field(ge=1, le=6)
    visible: bool = True
    default_input: int = Field(ge=1, le=6)
    max_volume: int = Field(100, ge=5, le=100)
    tv_id: Optional[str] = None
    sources: List[SourceItem] = []


class LayoutReq(BaseModel):
    rooms: List[RoomLayout]
    party_sources: List[SourceItem]
    wiims: Optional[List[WiimItem]] = None


async def _done(doc):
    await store(doc)
    return view(doc)


def _reconcile_party(doc, keep_rooms):
    """After a failed command keep only rooms the amp confirmed are on the party source."""
    p = doc["party"]
    if not p["active"]:
        return
    ok = [r for r in p["rooms"] if doc["status"][r]["power"] and doc["status"][r]["input"] == p["input"]]
    for r in [r for r in p["rooms"] if r not in ok]:
        p["saved"].pop(r, None)
    p["rooms"] = ok
    if not ok:
        p["active"], p["saved"], p["rooms"] = False, {}, keep_rooms


async def _guarded(doc, coro):
    keep = list(doc["party"]["rooms"])
    try:
        await coro
    except HTTPException:
        _reconcile_party(doc, keep)
        await store(doc)
        raise
    return await _done(doc)


@router.get("/listen")
async def get_listen():
    doc = await load()
    await sync(doc)
    return view(doc)


@router.post("/listen/sync")
async def post_sync():
    doc = await load()
    await sync(doc, force=True)
    if doc.get("amp_error"):
        raise HTTPException(424, doc["amp_error"])
    return view(doc)


@router.post("/listen/room/{rid}")
async def set_room(rid: str, req: RoomReq):
    doc = await load()
    r = room(doc, rid)
    ch = req.model_dump(exclude_none=True)
    src = None
    if "label" in ch or "input" in ch:
        src = find_source(r, ch.get("label"), ch.get("input"))
        if not src:
            raise HTTPException(400, f"{r['name']} can't select that source")
        ch["input"] = src["input"]
        if doc["party"]["active"] and rid in doc["party"]["rooms"]:
            raise HTTPException(409, f"{r['name']} is in Party Mode — remove it from the party to pick its own source")
        if not doc["status"][rid]["power"]:
            ch.setdefault("power", True)

    async def go():
        if src:
            await prepare_source(doc, src)
            doc["status"][rid]["source_label"] = src["label"]
        await apply(doc, {rid: ch})
    return await _guarded(doc, go())


@router.post("/listen/party")
async def set_party(req: PartyReq):
    doc = await load()
    if req.active == doc["party"]["active"]:
        return view(doc)
    return await _guarded(doc, party_on(doc) if req.active else party_off(doc))


@router.post("/listen/party/source")
async def set_party_source(req: PartySourceReq):
    doc = await load()
    if not doc["party"]["active"]:
        if req.input not in [s["input"] for s in doc["party_sources"]]:
            raise HTTPException(400, "Not a Party Mode source")
        doc["party"]["input"] = req.input
        return await _done(doc)
    return await _guarded(doc, party_on(doc, req.input))


@router.post("/listen/party/room/{rid}")
async def set_party_room(rid: str, req: PartyRoomReq):
    doc = await load()
    keep = list(doc["party"]["rooms"])

    async def go():
        await (party_join(doc, rid) if req.join else party_leave(doc, rid))
        _close_party_if_empty(doc, keep)
    return await _guarded(doc, go())


@router.post("/listen/party/master")
async def party_master(req: PartyMasterReq):
    doc = await load()
    p = doc["party"]
    if not p["active"]:
        raise HTTPException(400, "Party Mode is off")
    return await _guarded(doc, apply(doc, {rid: {"volume": doc["status"][rid]["volume"] + req.delta} for rid in p["rooms"]}))


_DEMO_TRACKS = {"wiim1": ("Sunday Morning", "Maroon 5"), "wiim2": ("Here Comes the Sun", "The Beatles")}
_demo_playing: Dict[str, bool] = {}


def _demo_wiim(wid):
    title, artist = _DEMO_TRACKS.get(wid, ("Demo track", "Demo artist"))
    return {"ip": "", "mode": "wifi", "mode_label": WIIM_MODES["wifi"], "playing": _demo_playing.get(wid, True),
            "title": title, "artist": artist, "demo": True}


@router.post("/listen/wiim/{wid}/play-pause")
async def wiim_play_pause(wid: str):
    doc = await load()
    w = next((x for x in doc["wiims"] if x["id"] == wid), None)
    if not w:
        raise HTTPException(404, "WiiM not found")
    entry = {"driver": "WiiM", "transport": "LinkPlay HTTP API", "command": linkplay.CMDS["play_pause"],
             "note": f"{w['name']} play/pause", "timestamp": _now()}
    if not live(doc):
        _demo_playing[wid] = not _demo_playing.get(wid, True)
        await log([{**entry, "status": "simulated"}])
        return _demo_wiim(wid)
    if not w.get("ip"):
        raise HTTPException(424, f"{w['name']} has no IP address yet — set it in Settings → Rooms & sources")
    try:
        await linkplay.command(w["ip"], "play_pause")
    except Exception as e:
        await log([{**entry, "status": "error", "error": str(e)}])
        raise HTTPException(424, f"{w['name']} not reachable at {w['ip']}: {e}")
    await log([{**entry, "status": "sent"}])
    await asyncio.sleep(0.4)
    try:
        return await wiim_status(wid)
    except HTTPException:
        return {"ip": w["ip"], "mode": "wifi", "mode_label": WIIM_MODES["wifi"], "playing": None, "title": "", "artist": ""}


@router.get("/listen/wiim/{wid}/status")
async def wiim_status(wid: str):
    doc = await load()
    w = next((x for x in doc["wiims"] if x["id"] == wid), None)
    if w and not live(doc):
        return _demo_wiim(wid)
    if not w or not w.get("ip"):
        raise HTTPException(404, "Set this WiiM's IP address and save first")
    try:
        st = await linkplay.status(w["ip"])
    except Exception as e:
        raise HTTPException(424, f"{w['name']} not reachable at {w['ip']}: {e}")
    code = str(st.get("mode"))
    mode = next((k for k, v in _WIIM_MODE_CODE.items() if v == code), "wifi")
    return {"ip": w["ip"], "mode": mode, "mode_label": WIIM_MODES[mode], "playing": st.get("status") == "play",
            "title": st.get("title"), "artist": st.get("artist")}


@router.post("/listen/restore-defaults")
async def post_restore_defaults():
    doc = await load()
    return await _guarded(doc, restore_defaults(doc))


@router.put("/listen/layout")
async def put_layout(req: LayoutReq):
    doc = await load()
    ids = [r.id for r in req.rooms]
    if len(set(ids)) != len(ids) or len({r.amp_zone for r in req.rooms}) != len(ids):
        raise HTTPException(400, "Each room needs a unique id and its own amp zone")
    wiims = [w.model_dump() for w in req.wiims] if req.wiims is not None else doc["wiims"]
    wids = {w["id"] for w in wiims}
    for r in req.rooms:
        if r.sources and r.default_input not in [s.input for s in r.sources]:
            raise HTTPException(400, f"{r.name}: the default source must be one of its sources")
        if len({s.label for s in r.sources}) != len(r.sources):
            raise HTTPException(400, f"{r.name}: each source needs a different name")
    for s_ in [s for r in req.rooms for s in r.sources] + list(req.party_sources):
        if s_.wiim and (s_.wiim not in wids or not s_.wiim_mode):
            raise HTTPException(400, f"{s_.label}: pick a WiiM and the mode it should switch to")
    if not req.party_sources:
        raise HTTPException(400, "Party Mode needs at least one source")
    doc["rooms"] = [r.model_dump() for r in req.rooms]
    doc["party_sources"] = [s.model_dump() for s in req.party_sources]
    doc["wiims"] = wiims
    doc["status"] = {k: v for k, v in doc["status"].items() if k in ids}
    p = doc["party"]
    p["rooms"] = [r for r in p["rooms"] if r in ids]
    if p["input"] not in [s.input for s in req.party_sources]:
        p["input"] = req.party_sources[0].input
    await store(doc)
    return view(await load())


# ---- shortcuts --------------------------------------------------------------
class RoomAction(BaseModel):
    label: Optional[str] = None
    power: Optional[bool] = None
    input: Optional[int] = Field(None, ge=1, le=6)
    volume: Optional[int] = Field(None, ge=0, le=100)
    mute: Optional[bool] = None


class PartyAction(BaseModel):
    enabled: bool
    input: Optional[int] = None
    rooms: Optional[List[str]] = None


class ShortcutReq(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    description: str = ""
    icon: str = "Sparkles"
    rooms: Dict[str, RoomAction] = {}
    party: Optional[PartyAction] = None
    restore_defaults: bool = False
    favorite: bool = False


class ReorderReq(BaseModel):
    ids: List[str]


def _clean(sc: dict) -> dict:
    sc["rooms"] = {k: {a: b for a, b in v.items() if b is not None} for k, v in (sc.get("rooms") or {}).items()}
    sc["rooms"] = {k: v for k, v in sc["rooms"].items() if v}
    return sc


async def _shortcuts():
    return await D["db"].shortcuts.find({}, {"_id": 0}).sort("order", 1).to_list(500)


async def seed_shortcuts():
    if await D["db"].meta.find_one({"key": "seed_shortcuts_v1"}):
        return
    for i, s in enumerate(DEFAULT_SHORTCUTS):
        await D["db"].shortcuts.insert_one({"id": str(uuid.uuid4()), "description": "", "party": None, "restore_defaults": False,
                                            **copy.deepcopy(s), "favorite": True, "order": i, "created_at": _now(), "updated_at": _now()})
    await D["db"].meta.insert_one({"key": "seed_shortcuts_v1"})


async def migrate_layout_v2():
    """One time: Office WiiM on input 5 (TV over Bluetooth + AirPlay), Bathroom WiiM on 6, party phone source on 3.
    Rooms or shortcuts the admin already edited are left alone."""
    db = D["db"]
    if await db.meta.find_one({"key": "listen_layout_v2_wiim"}):
        return
    doc = await db.listen.find_one(DOC, {"_id": 0})
    if doc:
        new = {r["id"]: r for r in DEFAULT_ROOMS}
        plain = lambda srcs: [{k: v for k, v in x.items() if v is not None} for x in (srcs or [])]
        for r in doc["rooms"]:
            if r["id"] in ("office", "bathroom") and plain(r.get("sources")) == _V1[r["id"]]:
                r["sources"], r["default_input"] = copy.deepcopy(new[r["id"]]["sources"]), new[r["id"]]["default_input"]
        if plain(doc.get("party_sources")) == _V1["party"]:
            doc["party_sources"] = copy.deepcopy(DEFAULT_PARTY_SOURCES)
            if not doc["party"]["active"] and doc["party"]["input"] == 6:
                doc["party"]["input"] = 3
        wiims = doc.get("wiims")
        if not wiims or all(not w.get("ip") and w["name"] in ("WiiM 1", "WiiM 2") for w in wiims):
            doc["wiims"] = copy.deepcopy(DEFAULT_WIIMS)
        await db.listen.update_one(DOC, {"$set": {k: doc[k] for k in ("rooms", "party_sources", "party", "wiims")}})
    await db.shortcuts.update_many({"name": "Music Everywhere", "party.input": 6}, {"$set": {"party.input": 3, "updated_at": _now()}})
    await db.meta.insert_one({"key": "listen_layout_v2_wiim"})


async def _get_sc(sid):
    sc = await D["db"].shortcuts.find_one({"id": sid}, {"_id": 0})
    if not sc:
        raise HTTPException(404, "Shortcut not found")
    return sc


@router.get("/shortcuts")
async def list_shortcuts():
    return await _shortcuts()


@router.post("/shortcuts")
async def create_shortcut(req: ShortcutReq):
    last = await D["db"].shortcuts.find_one({}, {"_id": 0, "order": 1}, sort=[("order", -1)])
    sc = _clean({"id": str(uuid.uuid4()), **req.model_dump(), "order": (last["order"] + 1) if last else 0,
                 "created_at": _now(), "updated_at": _now()})
    await D["db"].shortcuts.insert_one(copy.deepcopy(sc))
    return sc


@router.put("/shortcuts/{sid}")
async def update_shortcut(sid: str, req: ShortcutReq):
    await _get_sc(sid)
    await D["db"].shortcuts.update_one({"id": sid}, {"$set": {**_clean(req.model_dump()), "updated_at": _now()}})
    return await _get_sc(sid)


@router.delete("/shortcuts/{sid}")
async def delete_shortcut(sid: str):
    await _get_sc(sid)
    await D["db"].shortcuts.delete_one({"id": sid})
    return {"ok": True}


@router.post("/shortcuts/{sid}/duplicate")
async def duplicate_shortcut(sid: str):
    sc = await _get_sc(sid)
    return await create_shortcut(ShortcutReq(**{**sc, "name": f"{sc['name']} (copy)"[:60], "favorite": False}))


@router.post("/shortcuts/{sid}/favorite")
async def favorite_shortcut(sid: str, req: PartyReq):
    await _get_sc(sid)
    await D["db"].shortcuts.update_one({"id": sid}, {"$set": {"favorite": req.active, "updated_at": _now()}})
    return await _get_sc(sid)


@router.post("/shortcuts/reorder")
async def reorder_shortcuts(req: ReorderReq):
    existing = {s["id"] for s in await _shortcuts()}
    if set(req.ids) != existing or len(req.ids) != len(existing):
        raise HTTPException(400, "Send every shortcut id exactly once")
    for i, sid in enumerate(req.ids):
        await D["db"].shortcuts.update_one({"id": sid}, {"$set": {"order": i}})
    return await _shortcuts()


@router.post("/shortcuts/{sid}/run")
async def run_shortcut_api(sid: str):
    sc = await _get_sc(sid)
    doc = await load()
    return await _guarded(doc, run_shortcut(doc, sc))
