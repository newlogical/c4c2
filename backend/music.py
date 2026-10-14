"""TuneIn (RadioTime OPML) directory + Spotify Web API helpers."""
import asyncio
import time

import httpx
import spotipy
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.oauth2 import SpotifyOAuth

TUNEIN = "https://opml.radiotime.com"
SPOTIFY_SCOPES = "user-read-playback-state user-modify-playback-state user-read-private playlist-read-private user-read-recently-played"

# Pre-saved stations (user request: WFAN + big-4 sports + finance)
DEFAULT_STATIONS = [
    {"id": "wfan", "name": "WFAN Sports Radio 66 / 101.9", "kind": "url", "url": "https://live.amperwave.net/direct/audacy-wfanamaac-imc",
     "image": "", "category": "Sports"},
    {"id": "s25876", "name": "ESPN Radio", "kind": "tunein", "guide_id": "s25876", "image": "http://cdn-profiles.tunein.com/s25876/images/logoq.jpg", "category": "Sports"},
    {"id": "s28060", "name": "FOX Sports Radio", "kind": "tunein", "guide_id": "s28060", "image": "http://cdn-profiles.tunein.com/s28060/images/logoq.jpg", "category": "Sports"},
    {"id": "s353779", "name": "NBC Sports Radio", "kind": "tunein", "guide_id": "s353779", "image": "http://cdn-profiles.tunein.com/s353779/images/logoq.jpg", "category": "Sports"},
    {"id": "s165740", "name": "Bloomberg Radio", "kind": "tunein", "guide_id": "s165740", "image": "http://cdn-profiles.tunein.com/s165740/images/logoq.png", "category": "Finance"},
    {"id": "s110052", "name": "CNBC", "kind": "tunein", "guide_id": "s110052", "image": "http://cdn-profiles.tunein.com/s110052/images/logoq.jpg", "category": "Finance"},
    {"id": "s47135", "name": "Bloomberg TV (audio)", "kind": "tunein", "guide_id": "s47135", "image": "http://cdn-profiles.tunein.com/s47135/images/logoq.png", "category": "Finance"},
]
BROWSE = {"local": "c=local", "music": "c=music", "sports": "c=sports", "news": "c=news", "talk": "c=talk"}


def _station(x):
    return {"guide_id": x.get("guide_id"), "name": x.get("text"), "subtext": x.get("subtext") or "", "image": x.get("image") or ""}


def _flatten(body):
    out = []
    for x in body or []:
        if x.get("children"):
            out += _flatten(x["children"])
        elif x.get("type") == "audio" and x.get("item") == "station" and (x.get("guide_id") or "").startswith("s"):
            out.append(_station(x))
    return out


async def _opml(path: str, params: dict):
    async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
        r = await c.get(f"{TUNEIN}/{path}", params={**params, "render": "json"})
        r.raise_for_status()
        return r.json().get("body", [])


def _links(body):
    out = []
    for x in body or []:
        if x.get("children"):
            out += _links(x["children"])
        elif x.get("type") == "link" and "Browse.ashx" in (x.get("URL") or "") and "podcast" not in (x.get("text") or "").lower():
            q = dict(p.split("=", 1) for p in x["URL"].split("?", 1)[-1].split("&") if "=" in p)
            if q.get("id", "").startswith(("c", "g")):
                out.append({"id": q["id"], "name": x.get("text")})
    return out


async def search(q: str):
    return _flatten(await _opml("Search.ashx", {"query": q, "types": "station"}))[:40]


async def browse(cat: str):
    """cat: a top-level key (local/music/...) or a TuneIn category id (c123 / g45)."""
    params = dict([BROWSE[cat].split("=")]) if cat in BROWSE else {"id": cat}
    body = await _opml("Browse.ashx", params)
    return {"stations": _flatten(body)[:60], "categories": _links(body)[:30]}


async def resolve(station: dict) -> str:
    if station.get("kind") == "url":
        return station["url"]
    body = await _opml("Tune.ashx", {"id": station["guide_id"]})
    urls = [x["url"] for x in body if x.get("element") == "audio" and x.get("url")]
    if not urls:
        raise RuntimeError("TuneIn has no playable stream for this station")
    return urls[0]


def stream_command(url: str) -> str:
    return "setPlayerCmd:play:" + url  # httpx percent-encodes the whole command param


# ---------------------------------------------------------------------------
# Spotify (spotipy, authorization-code flow; token persisted by the caller)
def oauth(conf: dict, token: dict | None = None, state: str | None = None):
    return SpotifyOAuth(client_id=conf["client_id"], client_secret=conf["client_secret"], redirect_uri=conf["redirect_uri"],
                        scope=SPOTIFY_SCOPES, state=state, cache_handler=MemoryCacheHandler(token_info=token), open_browser=False)


def client(conf: dict, token: dict):
    """Returns (spotipy client, possibly-refreshed token)."""
    o = oauth(conf, token)
    if token.get("expires_at", 0) - int(time.time()) < 60:
        token = o.refresh_access_token(token["refresh_token"])
    return spotipy.Spotify(auth=token["access_token"], requests_timeout=8), token


def library(sp):
    me = sp.me()
    pls = sp.current_user_playlists(limit=30).get("items", [])
    recent = sp.current_user_recently_played(limit=30).get("items", [])
    seen, ctx = set(), []
    for it in recent:
        c = it.get("context") or {}
        if c.get("uri") and c["uri"] not in seen and c.get("type") in ("album", "playlist", "artist"):
            seen.add(c["uri"])
            t = it["track"]
            ctx.append({"uri": c["uri"], "name": t["album"]["name"] if c["type"] == "album" else t["artists"][0]["name"] if c["type"] == "artist" else "Recent playlist",
                        "kind": c["type"], "image": (t["album"].get("images") or [{}])[0].get("url", "")})
    return {
        "user": me.get("display_name") or me.get("id"), "premium": me.get("product") == "premium",
        "playlists": [{"uri": p["uri"], "name": p["name"], "kind": "playlist", "image": (p.get("images") or [{}])[0].get("url", "") if p.get("images") else ""}
                      for p in pls if p],
        "recent": ctx[:12],
    }


def play_on(sp, device_name: str, uri: str):
    devices = sp.devices().get("devices", [])
    dev = next((d for d in devices if d["name"].lower() == device_name.lower()), None) or \
        next((d for d in devices if device_name.lower() in d["name"].lower()), None)
    if not dev:
        names = ", ".join(d["name"] for d in devices) or "none"
        raise RuntimeError(f"Spotify can't see '{device_name}'. Open Spotify once and pick it as a speaker. Visible: {names}")
    sp.start_playback(device_id=dev["id"], context_uri=uri)


async def run(fn, *a):
    return await asyncio.to_thread(fn, *a)
