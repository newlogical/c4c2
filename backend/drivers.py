"""
Hardware driver abstraction layer.

Each driver formats the exact wire protocol command for its device, records it
in the command log, and — when that device is configured `live` — actually
dispatches it over the LAN (socket/Telnet, pyws66i, Ecobee REST, pyatv CLI).
When a device is not live (default / cloud demo, or if the transport fails) the
command is logged with status "simulated" / "error" and application state still
updates, so the UI always stays responsive.

Live config is passed per-call as `conn` (a dict from state['config'][device]).
"""
import socket
import shutil
import subprocess
from datetime import datetime, timezone


def _ts():
    return datetime.now(timezone.utc).isoformat()


class BaseDriver:
    name = "base"
    transport = "n/a"

    def _dispatch(self, payload, note, conn, sender=None):
        entry = {
            "driver": self.name,
            "transport": self.transport,
            "command": payload,
            "note": note,
            "timestamp": _ts(),
            "status": "simulated",
        }
        if conn and conn.get("live") and sender:
            try:
                sender()
                entry["status"] = "sent"
            except Exception as e:  # never let hardware faults break the app
                entry["status"] = "error"
                entry["error"] = str(e)[:200]
        return entry

    def command(self, payload, note="", conn=None):
        return self._dispatch(payload, note, conn)


class MatrixDriver(BaseDriver):
    """J-Tech JTECH-MXT40 4x4 HDBaseT Matrix — Telnet TCP:23, '#video_d outN matrix=I'."""

    name = "JTECH-MXT40"
    transport = "Telnet TCP:23"

    def _send(self, conn, payload):
        host = conn["host"]
        port = int(conn.get("port", 23))
        with socket.create_connection((host, port), timeout=4) as s:
            s.sendall((payload + "\r\n").encode())

    def route(self, output_index, input_index, display, source, conn=None):
        payload = f"#video_d out{output_index} matrix={input_index}"
        return self._dispatch(payload, f"Route {source} -> {display}", conn,
                              sender=lambda: self._send(conn, payload))

    def power(self, output_index, on, display, conn=None):
        payload = f"#display out{output_index} {'on' if on else 'off'}"
        return self._dispatch(payload, f"{display} power {'ON' if on else 'OFF'}", conn,
                              sender=lambda: self._send(conn, payload))


class AmpDriver(BaseDriver):
    """Soundavo WS66i 6-Zone Amplifier — Telnet/IP via pyws66i (zones 11-16)."""

    name = "WS66i"
    transport = "Telnet TCP (pyws66i)"

    def _client(self, conn):
        from pyws66i import get_ws66i  # lazy: only needed live
        c = get_ws66i(conn["host"])
        c.open()
        return c

    def set_source(self, zone, src, zone_name, source_name, conn=None):
        payload = f"<{10 + zone:02d}CH{src:02d}"

        def send():
            c = self._client(conn)
            try:
                c.set_source(10 + zone, src)
            finally:
                c.close()
        return self._dispatch(payload, f"{zone_name} source -> {source_name}", conn, sender=send)

    def set_volume(self, zone, vol_0_38, zone_name, pct, conn=None):
        payload = f"<{10 + zone:02d}VO{vol_0_38:02d}"

        def send():
            c = self._client(conn)
            try:
                c.set_volume(10 + zone, vol_0_38)
            finally:
                c.close()
        return self._dispatch(payload, f"{zone_name} volume -> {pct}%", conn, sender=send)

    def set_mute(self, zone, mute, zone_name, conn=None):
        payload = f"<{10 + zone:02d}MU{'01' if mute else '00'}"

        def send():
            c = self._client(conn)
            try:
                c.set_mute(10 + zone, mute)
            finally:
                c.close()
        return self._dispatch(payload, f"{zone_name} {'muted' if mute else 'unmuted'}", conn, sender=send)

    def set_power(self, zone, on, zone_name, conn=None):
        payload = f"<{10 + zone:02d}PR{'01' if on else '00'}"

        def send():
            c = self._client(conn)
            try:
                c.set_power(10 + zone, on)
            finally:
                c.close()
        return self._dispatch(payload, f"{zone_name} power {'ON' if on else 'OFF'}", conn, sender=send)


class AppleTVDriver(BaseDriver):
    """Apple TV — pyatv `atvremote` CLI over the LAN."""

    name = "AppleTV"
    transport = "pyatv MRP / AirPlay"

    _KEYS = {
        "up", "down", "left", "right", "select", "menu", "home",
        "play_pause", "pause", "play", "volume_up", "volume_down",
    }

    def key(self, source_name, key, conn=None, device=None):
        payload = f"atvremote --id <id> {key}"

        def send():
            dev = (conn.get("devices") or {}).get(device or "", {})
            if key not in self._KEYS or not dev.get("id"):
                raise RuntimeError("device not configured / unsupported key")
            if not shutil.which("atvremote"):
                raise RuntimeError("pyatv (atvremote) not installed")
            cmd = ["atvremote", "--id", dev["id"]]
            if dev.get("credentials"):
                cmd += ["--companion-credentials", dev["credentials"]]
            cmd.append(key)
            subprocess.run(cmd, timeout=6, check=True, capture_output=True)
        return self._dispatch(payload, f"{source_name}: {key}", conn, sender=send)


class ThermostatDriver(BaseDriver):
    """Ecobee Smart Thermostat — HTTPS REST api.ecobee.com/1/thermostat."""

    name = "Ecobee"
    transport = "HTTPS REST"

    def _post(self, conn, body, desc):
        import requests
        url = "https://api.ecobee.com/1/thermostat?format=json"
        headers = {
            "Authorization": f"Bearer {conn.get('token', '')}",
            "Content-Type": "application/json;charset=UTF-8",
        }
        r = requests.post(url, json=body, headers=headers, timeout=8)
        r.raise_for_status()

    def set_mode(self, mode, conn=None):
        body = {
            "selection": {"selectionType": "registered", "selectionMatch": ""},
            "thermostat": {"settings": {"hvacMode": mode}},
        }
        return self._dispatch(f'POST /1/thermostat settings.hvacMode="{mode}"',
                              f"Set mode = {mode}", conn, sender=lambda: self._post(conn, body, "mode"))

    def set_fan(self, fan, conn=None):
        body = {
            "selection": {"selectionType": "registered", "selectionMatch": ""},
            "thermostat": {"settings": {"vent": fan}},
        }
        return self._dispatch(f'POST /1/thermostat settings.fan="{fan}"',
                              f"Set fan = {fan}", conn, sender=lambda: self._post(conn, body, "fan"))

    def set_hold(self, heat_f, cool_f, conn=None):
        body = {
            "selection": {"selectionType": "registered", "selectionMatch": ""},
            "functions": [{
                "type": "setHold",
                "params": {"holdType": "nextTransition",
                           "heatHoldTemp": int(heat_f * 10),
                           "coolHoldTemp": int(cool_f * 10)},
            }],
        }
        return self._dispatch(f'POST /1/thermostat setHold heat={heat_f} cool={cool_f}',
                              f"Hold heat {heat_f}° / cool {cool_f}°", conn,
                              sender=lambda: self._post(conn, body, "hold"))


class CameraDriver(BaseDriver):
    """Ubiquiti UniFi Protect camera — RTSP / Protect API."""

    name = "UniFi-Protect"
    transport = "RTSP :7447 / Protect API"

    def snapshot(self, cam_name, conn=None):
        payload = "GET /proxy/protect/api/cameras/<id>/snapshot"
        return self._dispatch(payload, f"{cam_name}: snapshot", conn)


class TVDriver(BaseDriver):
    """Samsung Tizen TV — samsungtvws WebSocket for keys/power-off, Wake-on-LAN for power-on."""

    name = "SamsungTV"
    transport = "WS :8001 + WoL"

    def _wol(self, mac):
        clean = mac.replace(":", "").replace("-", "").strip()
        if len(clean) != 12:
            raise RuntimeError("Invalid MAC address")
        packet = bytes.fromhex("f" * 12 + clean * 16)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(packet, ("255.255.255.255", 9))
        finally:
            s.close()

    def _tv(self, conn):
        from samsungtvws import SamsungTVWS  # lazy: only needed live
        return SamsungTVWS(host=conn["ip"], token=conn.get("token") or None, timeout=6)

    def power(self, output_display, on, conn=None):
        if on:
            payload = f"WoL magic packet -> {conn.get('mac','?') if conn else '?'}"
            note = f"{output_display} power ON (Wake-on-LAN) + HDMI{conn.get('hdmi_input','?') if conn else '?'}"

            def send():
                self._wol(conn["mac"])
                if conn.get("hdmi_input"):
                    self._tv(conn).send_key("KEY_HDMI")  # each TV sits on its fixed matrix output
        else:
            payload = "send_key KEY_POWER"
            note = f"{output_display} power OFF"

            def send():
                self._tv(conn).send_key("KEY_POWER")
        return self._dispatch(payload, note, conn, sender=send)

    def key(self, display_name, key, conn=None):
        payload = f"send_key {key}"
        return self._dispatch(payload, f"{display_name}: {key}", conn,
                              sender=lambda: self._tv(conn).send_key(key))


matrix = MatrixDriver()
amp = AmpDriver()
appletv = AppleTVDriver()
thermostat = ThermostatDriver()
camera = CameraDriver()
tv = TVDriver()

# A public test HLS feed so the live player streams video in the cloud demo.
DEMO_HLS = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
