"""Linkplay HTTP API client for the WS66i built-in streaming modules (Arylic/Linkplay)."""
import binascii

import httpx

TIMEOUT = 3.0
_scheme: dict = {}


def _unhex(v):
    # Older firmware hex-encodes Title/Artist/Album in getPlayerStatus
    if not isinstance(v, str) or not v or len(v) % 2:
        return v or ""
    try:
        return binascii.unhexlify(v).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return v


async def _get(ip: str, command: str):
    schemes = [_scheme[ip]] if ip in _scheme else ["https", "http"]
    last = None
    for sch in schemes:
        try:
            async with httpx.AsyncClient(verify=False, timeout=TIMEOUT) as c:
                r = await c.get(f"{sch}://{ip}/httpapi.asp", params={"command": command})
                r.raise_for_status()
                _scheme[ip] = sch
                try:
                    return r.json()
                except ValueError:
                    return r.text.strip()
        except Exception as e:
            last = e
            _scheme.pop(ip, None)
    raise RuntimeError(f"Streaming module {ip} not reachable") from last


async def status(ip: str) -> dict:
    st = await _get(ip, "getPlayerStatus")
    st = st if isinstance(st, dict) else {}
    out = {"status": st.get("status", "stop"), "vol": int(st.get("vol", 0) or 0), "mode": st.get("mode"),
           "title": _unhex(st.get("Title")), "artist": _unhex(st.get("Artist")), "album": _unhex(st.get("Album")), "art": ""}
    try:
        meta = (await _get(ip, "getMetaInfo") or {}).get("metaData") or {}
        for k, mk in (("title", "title"), ("artist", "artist"), ("album", "album"), ("art", "albumArtURI")):
            if meta.get(mk) and meta[mk] != "unknow":
                out[k] = meta[mk]
    except Exception:
        pass
    return out


async def presets(ip: str) -> list:
    data = await _get(ip, "getPresetInfo")
    items = (data or {}).get("preset_list") if isinstance(data, dict) else None
    return [{"number": int(p.get("number", i + 1)), "name": p.get("name") or f"Preset {i + 1}",
             "source": p.get("source", ""), "art": p.get("picurl", "")} for i, p in enumerate(items or [])]


async def play_preset(ip: str, number: int):
    await _get(ip, f"MCUKeyShortClick:{number}")


CMDS = {"play_pause": "setPlayerCmd:onepause", "next": "setPlayerCmd:next", "prev": "setPlayerCmd:prev",
        "stop": "setPlayerCmd:stop", "play": "setPlayerCmd:resume", "pause": "setPlayerCmd:pause"}


async def command(ip: str, cmd: str, value: int | None = None):
    if cmd == "volume":
        await _get(ip, f"setPlayerCmd:vol:{max(0, min(100, int(value or 0)))}")
    else:
        await _get(ip, CMDS[cmd])
