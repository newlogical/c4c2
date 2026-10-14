"""UniFi Protect PTZ: official Integration API (presets/patrol) + experimental private API (continuous move)."""
import asyncio
import httpx

PUBLIC = "/proxy/protect/integration/v1"
PRIVATE = "/proxy/protect/api"
SPEED_MAX = 1000


def _norm_mac(mac: str) -> str:
    return "".join(ch for ch in (mac or "") if ch.isalnum()).lower()


class ProtectPTZ:
    def __init__(self):
        self._cam_ids = {}
        self._session = None  # (cookies, csrf)
        self._stop_task = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _client(nvr_ip, **kw):
        return httpx.AsyncClient(base_url=f"https://{nvr_ip}", verify=False, timeout=httpx.Timeout(8.0, connect=4.0), **kw)

    async def _public(self, conn, method, path):
        if not conn.get("protect_api_key"):
            raise RuntimeError("Add the Protect API key in Settings → UniFi Camera")
        async with self._client(conn["nvr_ip"], headers={"X-API-KEY": conn["protect_api_key"], "Accept": "application/json"}) as c:
            r = await c.request(method, path)
            r.raise_for_status()
            return r.json() if r.content else None

    async def camera_id(self, conn):
        key = (conn["nvr_ip"], _norm_mac(conn["mac"]))
        if key not in self._cam_ids:
            cams = await self._public(conn, "GET", f"{PUBLIC}/cameras")
            cams = cams.get("data", cams) if isinstance(cams, dict) else cams
            match = next((c for c in cams if _norm_mac(c.get("mac")) == key[1]), None)
            if not match:
                raise RuntimeError(f"Camera {conn['mac']} not found in Protect")
            self._cam_ids[key] = match["id"]
        return self._cam_ids[key]

    async def goto(self, conn, slot: int):
        cid = await self.camera_id(conn)
        await self._public(conn, "POST", f"{PUBLIC}/cameras/{cid}/ptz/goto/{slot}")

    async def patrol(self, conn, start: bool, slot: int = 0):
        cid = await self.camera_id(conn)
        path = f"ptz/patrol/start/{slot}" if start else "ptz/patrol/stop"
        await self._public(conn, "POST", f"{PUBLIC}/cameras/{cid}/{path}")

    async def _login(self, conn):
        if not (conn.get("protect_user") and conn.get("protect_password")):
            raise RuntimeError("Arrow/zoom controls need a local Protect user + password in Settings")
        async with self._client(conn["nvr_ip"]) as c:
            r = await c.post("/api/auth/login", json={"username": conn["protect_user"], "password": conn["protect_password"], "rememberMe": True})
            r.raise_for_status()
            self._session = (dict(r.cookies), r.headers.get("x-csrf-token", ""))

    async def _private_post(self, conn, path, body, retry=True):
        if not self._session:
            await self._login(conn)
        cookies, csrf = self._session
        async with self._client(conn["nvr_ip"], cookies=cookies, headers={"X-CSRF-Token": csrf}) as c:
            r = await c.post(f"{PRIVATE}{path}", json=body)
        if r.status_code in (401, 403) and retry:
            self._session = None
            return await self._private_post(conn, path, body, retry=False)
        r.raise_for_status()

    async def move(self, conn, pan: int, tilt: int, zoom: int):
        clamp = lambda v: max(-SPEED_MAX, min(SPEED_MAX, int(v)))  # noqa: E731
        cid = await self.camera_id(conn)
        body = {"type": "continuous", "payload": {"x": clamp(pan), "y": clamp(tilt), "z": clamp(zoom)}}
        async with self._lock:
            await self._private_post(conn, f"/cameras/{cid}/move", body)
        if self._stop_task:
            self._stop_task.cancel()
        if any((pan, tilt, zoom)):  # dead-man: stop if the panel stops sending
            self._stop_task = asyncio.create_task(self._auto_stop(conn, cid))

    async def _auto_stop(self, conn, cid):
        await asyncio.sleep(1.5)
        try:
            await self._private_post(conn, f"/cameras/{cid}/move", {"type": "continuous", "payload": {"x": 0, "y": 0, "z": 0}})
        except Exception:
            pass


ptz = ProtectPTZ()
