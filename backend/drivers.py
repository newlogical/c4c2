"""
Hardware driver abstraction layer.

Each driver formats the exact wire protocol command for its device, records it
in the command log, and — when that device is configured `live` — actually
dispatches it over the LAN (socket/Telnet, pyws66i, HomeKit HAP, pyatv CLI).
When a device is not live (default / cloud demo, or if the transport fails) the
command is logged with status "simulated" / "error" and application state still
updates, so the UI always stays responsive.

Live config is passed per-call as `conn` (a dict from state['config'][device]).
"""
import socket
import shutil
import subprocess
import time
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
            self._login(s, conn)
            s.sendall((payload + "\r\n").encode())

    @staticmethod
    def _read(s, wait=0.8):
        s.settimeout(wait)
        try:
            return s.recv(1024).decode(errors="ignore").lower()
        except socket.timeout:
            return ""

    def _login(self, s, conn):
        # Answer a Telnet login prompt only if the matrix presents one
        banner = self._read(s)
        if "login" in banner or "user" in banner:
            s.sendall((conn.get("username", "") + "\r\n").encode())
            banner = self._read(s, 1.5)
        if "pass" in banner:
            s.sendall((conn.get("password", "") + "\r\n").encode())
            self._read(s, 1.5)

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
        dev = ((conn or {}).get("devices") or {}).get(device or "", {})
        target = f"-s {dev['ip']}" if dev.get("ip") else "--id <id>"
        payload = f"atvremote {target} {key}"

        def send():
            if key not in self._KEYS or not (dev.get("ip") or dev.get("id")):
                raise RuntimeError("device not configured / unsupported key")
            if not shutil.which("atvremote"):
                raise RuntimeError("pyatv (atvremote) not installed")
            cmd = ["atvremote", "-s", dev["ip"]] if dev.get("ip") else ["atvremote", "--id", dev["id"]]
            if dev.get("id") and dev.get("ip"):
                cmd += ["--id", dev["id"]]
            if dev.get("credentials"):
                cmd += ["--companion-credentials", dev["credentials"]]
            if dev.get("airplay_credentials"):
                cmd += ["--airplay-credentials", dev["airplay_credentials"]]
            cmd.append(key)
            subprocess.run(cmd, timeout=6, check=True, capture_output=True)
        return self._dispatch(payload, f"{source_name}: {key}", conn, sender=send)


class ThermostatDriver(BaseDriver):
    """Ecobee Smart Thermostat Premium — local HomeKit (HAP/IP) via aiohomekit."""

    name = "Ecobee"
    transport = "HomeKit HAP/IP (LAN)"

    def _send(self, values):
        import homekit
        homekit.thermostat.write(values)

    def set_mode(self, mode, conn=None):
        import homekit
        hap = homekit.MODE_TO_HAP.get(mode)
        return self._dispatch(f"PUT TargetHeatingCoolingState={hap} ({mode})", f"Set mode = {mode}", conn,
                              sender=lambda: self._send({"target_state": hap}))

    def set_fan(self, fan, conn=None):
        values = {"target_fan": 1} if fan == "auto" else {"target_fan": 0, "fan_active": 1}
        return self._dispatch(f"PUT Fan {values}", f"Set fan = {fan}", conn, sender=lambda: self._send(values))

    def set_hold(self, heat_f, cool_f, conn=None, mode=None):
        import homekit
        values = {"heat_threshold": homekit.f_to_c(heat_f), "cool_threshold": homekit.f_to_c(cool_f)}
        if mode in ("heat", "cool"):
            values["target_temp"] = homekit.f_to_c(heat_f if mode == "heat" else cool_f)
        return self._dispatch(f"PUT thresholds heat={values['heat_threshold']}C cool={values['cool_threshold']}C",
                              f"Hold heat {heat_f}° / cool {cool_f}°", conn, sender=lambda: self._send(values))


class CameraDriver(BaseDriver):
    """Ubiquiti UniFi Protect camera — RTSP / Protect API."""

    name = "UniFi-Protect"
    transport = "RTSP :7447 / Protect API"

    def snapshot(self, cam_name, conn=None):
        payload = "GET /proxy/protect/api/cameras/<id>/snapshot"
        return self._dispatch(payload, f"{cam_name}: snapshot", conn)


class SonyBraviaDriver(BaseDriver):
    """Sony Bravia Android TV (e.g. KD-49X7000E) — Bravia REST API with X-Auth-PSK,
    IRCC-IP for remote keys, Wake-on-LAN for power-on ("Remote start")."""

    name = "SonyBravia"
    transport = "Bravia REST + IRCC + WoL"

    _IRCC = {
        "KEY_POWER": "AAAAAQAAAAEAAAAvAw==",     # power off
        "KEY_VOLUP": "AAAAAQAAAAEAAAASAw==",
        "KEY_VOLDOWN": "AAAAAQAAAAEAAAATAw==",
        "KEY_MUTE": "AAAAAQAAAAEAAAAUAw==",
        "KEY_HOME": "AAAAAQAAAAEAAABgAw==",
        "KEY_UP": "AAAAAQAAAAEAAAB0Aw==",
        "KEY_DOWN": "AAAAAQAAAAEAAAB1Aw==",
        "KEY_LEFT": "AAAAAQAAAAEAAAA0Aw==",
        "KEY_RIGHT": "AAAAAQAAAAEAAAAzAw==",
        "KEY_ENTER": "AAAAAQAAAAEAAABlAw==",
        "KEY_1": "AAAAAQAAAAEAAAAAAw==", "KEY_2": "AAAAAQAAAAEAAAABAw==", "KEY_3": "AAAAAQAAAAEAAAACAw==",
        "KEY_4": "AAAAAQAAAAEAAAADAw==", "KEY_5": "AAAAAQAAAAEAAAAEAw==", "KEY_6": "AAAAAQAAAAEAAAAFAw==",
        "KEY_7": "AAAAAQAAAAEAAAAGAw==", "KEY_8": "AAAAAQAAAAEAAAAHAw==", "KEY_9": "AAAAAQAAAAEAAAAIAw==",
        "KEY_0": "AAAAAQAAAAEAAAAJAw==",
        "KEY_BACK": "AAAAAgAAAJcAAAAjAw==",
        "KEY_INPUT": "AAAAAQAAAAEAAAAlAw==",
        "KEY_GUIDE": "AAAAAQAAAKQAAABbAw==",
        "KEY_PLAY": "AAAAAgAAAJcAAAAaAw==",
        "KEY_PAUSE": "AAAAAgAAAJcAAAAZAw==",
        "KEY_CHUP": "AAAAAQAAAAEAAAAQAw==",
        "KEY_CHDOWN": "AAAAAQAAAAEAAAARAw==",
        "KEY_OPTIONS": "AAAAAgAAAJcAAAA2Aw==",
        "KEY_NETFLIX": "AAAAAgAAABoAAAB8Aw==",
        "KEY_YOUTUBE": "AAAAAgAAAMQAAABHAw==",
    }

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

    def _rest(self, conn, service, method, params):
        import requests
        if not conn.get("ip"):
            raise RuntimeError("TV IP not configured")
        url = f"http://{conn['ip']}/sony/{service}"
        headers = {"X-Auth-PSK": conn.get("psk", ""), "Content-Type": "application/json"}
        body = {"method": method, "id": 1, "version": "1.0", "params": params}
        r = requests.post(url, json=body, headers=headers, timeout=6)
        r.raise_for_status()
        if (r.json() or {}).get("error"):
            raise RuntimeError(f"Bravia error {r.json()['error']}")

    def _ircc(self, conn, code):
        import requests
        if not conn.get("ip"):
            raise RuntimeError("TV IP not configured")
        soap = (
            '<?xml version="1.0"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            '<u:X_SendIRCC xmlns:u="urn:schemas-sony-com:service:IRCC:1">'
            f'<IRCCCode>{code}</IRCCCode></u:X_SendIRCC></s:Body></s:Envelope>'
        )
        headers = {
            "X-Auth-PSK": conn.get("psk", ""),
            "Content-Type": "text/xml; charset=UTF-8",
            "SOAPACTION": '"urn:schemas-sony-com:service:IRCC:1#X_SendIRCC"',
        }
        r = requests.post(f"http://{conn['ip']}/sony/IRCC", data=soap.encode(), headers=headers, timeout=6)
        r.raise_for_status()

    def power(self, output_display, on, conn=None, select_input=True):
        if on:
            hdmi = conn.get("hdmi_input", "?") if conn else "?"
            payload = f"WoL -> {conn.get('mac','?') if conn else '?'} + setPowerStatus true"
            note = f"{output_display} power ON (Wake-on-LAN)" + (f" + HDMI{hdmi}" if select_input else "")

            def send():
                self._wol(conn["mac"])
                last = None
                for _ in range(4):  # TV network wakes a few seconds after WoL
                    try:
                        self._rest(conn, "system", "setPowerStatus", [{"status": True}])
                        if select_input and conn.get("hdmi_input"):
                            self._rest(conn, "avContent", "setPlayContent",
                                       [{"uri": f"extInput:hdmi?port={int(conn['hdmi_input'])}"}])
                        return
                    except Exception as e:
                        last = e
                        time.sleep(2)
                raise last
        else:
            payload = "setPowerStatus false"
            note = f"{output_display} power OFF"

            def send():
                self._rest(conn, "system", "setPowerStatus", [{"status": False}])
        return self._dispatch(payload, note, conn, sender=send)

    def set_input(self, display, port, conn=None):
        uri = f"extInput:hdmi?port={int(port)}"
        return self._dispatch(f"setPlayContent {uri}", f"{display} input -> HDMI{port}", conn,
                              sender=lambda: self._rest(conn, "avContent", "setPlayContent", [{"uri": uri}]))

    def set_volume(self, display, vol, conn=None):
        vol = max(0, min(100, int(vol)))
        return self._dispatch(f"setAudioVolume {vol}", f"{display} volume -> {vol}%", conn,
                              sender=lambda: self._rest(conn, "audio", "setAudioVolume",
                                                        [{"target": "speaker", "volume": str(vol)}]))

    def key(self, display_name, key, conn=None):
        code = self._IRCC.get(key)

        def send():
            if not code:
                raise RuntimeError(f"Unsupported key {key}")
            self._ircc(conn, code)
        return self._dispatch(f"IRCC {key}", f"{display_name}: {key}", conn, sender=send)


matrix = MatrixDriver()
amp = AmpDriver()
appletv = AppleTVDriver()
thermostat = ThermostatDriver()
camera = CameraDriver()
tv = SonyBraviaDriver()

# A public test HLS feed so the live player streams video in the cloud demo.
DEMO_HLS = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
