"""Local HomeKit (HAP over IP) controller for the Ecobee thermostat via aiohomekit."""
import asyncio
import re
import threading

ALIAS = "ecobee"
SVC_THERMOSTAT = "4A"
SVC_FAN = "B7"
CHARS = {
    "current_temp": "11", "target_temp": "35", "humidity": "10",
    "heat_threshold": "12", "cool_threshold": "D",
    "current_state": "F", "target_state": "33",
    "fan_active": "B0", "target_fan": "BF",
}
MODE_TO_HAP = {"off": 0, "heat": 1, "cool": 2, "auto": 3}
HAP_TO_MODE = {v: k for k, v in MODE_TO_HAP.items()}


def f_to_c(f):
    return round((float(f) - 32) * 5 / 9 * 2) / 2


def c_to_f(c):
    return round(float(c) * 9 / 5 + 32)


def normalize_code(code: str) -> str:
    digits = re.sub(r"\D", "", code or "")
    if len(digits) != 8:
        raise ValueError("HomeKit setup code must be 8 digits")
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


def _short(uuid: str) -> str:
    u = uuid.upper()
    if u.endswith("-0000-1000-8000-0026BB765291"):
        u = u.split("-")[0].lstrip("0") or "0"
    return u


class HomeKitThermostat:
    def __init__(self):
        self._loop = None
        self._controller = None
        self._zc = None
        self._browser = None
        self.pairing = None
        self._ids = None
        self._lock = threading.Lock()

    def _run(self, coro, timeout=40):
        with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                threading.Thread(target=self._loop.run_forever, daemon=True).start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=timeout)

    async def _ensure_controller(self):
        if self._controller:
            return
        from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
        from zeroconf import ServiceListener
        from aiohomekit import Controller

        class _L(ServiceListener):
            def add_service(self, *a): pass
            def remove_service(self, *a): pass
            def update_service(self, *a): pass

        self._zc = AsyncZeroconf()
        self._browser = AsyncServiceBrowser(self._zc.zeroconf, ["_hap._tcp.local.", "_hap._udp.local."], listener=_L())
        self._controller = Controller(async_zeroconf_instance=self._zc)
        await self._controller.async_start()

    def load(self, pairing_data: dict):
        async def go():
            await self._ensure_controller()
            self.pairing = self._controller.load_pairing(ALIAS, dict(pairing_data))
            self._ids = None
        self._run(go())

    def pair(self, ip: str, code: str) -> dict:
        code = normalize_code(code)

        async def go():
            await self._ensure_controller()
            target = None
            for _ in range(20):
                async for d in self._controller.async_discover():
                    desc = d.description
                    if ip in set(getattr(desc, "addresses", []) or []) | {getattr(desc, "address", None)}:
                        target = d
                        break
                if target:
                    break
                await asyncio.sleep(0.5)
            if not target:
                raise RuntimeError(f"No HomeKit accessory advertising at {ip} (check same LAN, mDNS, firewall)")
            finish = await target.async_start_pairing(ALIAS)
            self.pairing = await finish(code)
            self._ids = None
            return dict(self.pairing.pairing_data)
        return self._run(go(), timeout=60)

    def unpair(self):
        async def go():
            if self.pairing:
                try:
                    await self._controller.remove_pairing(ALIAS)
                finally:
                    self.pairing = None
                    self._ids = None
        self._run(go())

    async def _map(self):
        if self._ids:
            return self._ids
        accessories = await self.pairing.list_accessories_and_characteristics()
        ids = {}
        for acc in accessories:
            services = acc.get("services", [])
            if not any(_short(s.get("type", "")) == SVC_THERMOSTAT for s in services):
                continue
            for s in services:
                stype = _short(s.get("type", ""))
                if stype not in (SVC_THERMOSTAT, SVC_FAN):
                    continue
                for ch in s.get("characteristics", []):
                    ct = _short(ch.get("type", ""))
                    for name, short in CHARS.items():
                        if ct == short and (name not in ids or stype == SVC_THERMOSTAT):
                            ids[name] = (acc["aid"], ch["iid"])
            break
        if not ids:
            raise RuntimeError("No HomeKit thermostat service found on accessory")
        self._ids = ids
        return ids

    def read(self) -> dict:
        async def go():
            ids = await self._map()
            res = await self.pairing.get_characteristics(list(ids.values()))
            return {n: (res.get(cid) or {}).get("value") for n, cid in ids.items()}
        if not self.pairing:
            raise RuntimeError("Thermostat is not paired")
        return self._run(go())

    def write(self, values: dict) -> None:
        async def go():
            ids = await self._map()
            missing = [k for k in values if k not in ids]
            writes = [(*ids[k], v) for k, v in values.items() if k in ids]
            if writes:
                await self.pairing.put_characteristics(writes)
            if missing and not writes:
                raise RuntimeError(f"Thermostat does not expose: {', '.join(missing)}")
        if not self.pairing:
            raise RuntimeError("Thermostat is not paired")
        self._run(go())


thermostat = HomeKitThermostat()
