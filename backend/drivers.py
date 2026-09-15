"""
Hardware driver abstraction layer.

In DEMO mode every driver only formats + logs the exact protocol command it
*would* send to real hardware, then returns success. To go live on a
Raspberry Pi / mini-PC on the apartment LAN, implement the `send()` method of
each driver with the real transport (RS-232 serial, Telnet/TCP, REST, RTSP)
and flip DEMO_MODE off. The rest of the application does not change.
"""
from datetime import datetime, timezone


def _ts():
    return datetime.now(timezone.utc).isoformat()


class BaseDriver:
    name = "base"
    transport = "n/a"

    def command(self, payload: str, note: str = ""):
        """Return a structured command-log entry (demo) instead of sending."""
        return {
            "driver": self.name,
            "transport": self.transport,
            "command": payload,
            "note": note,
            "timestamp": _ts(),
        }


class MatrixDriver(BaseDriver):
    """J-Tech Digital JTECH-MXT40 4x4 HDMI/HDBaseT Matrix (Telnet / RS-232)."""

    name = "JTECH-MXT40"
    transport = "Telnet TCP:23 / RS-232"

    def route(self, output_index: int, input_index: int, display: str, source: str):
        # JTECH ASCII command set: e.g. "OUT02:03." routes input 3 -> output 2
        payload = f"OUT{output_index:02d}:{input_index:02d}."
        return self.command(payload, f"Route {source} -> {display}")


class AmpDriver(BaseDriver):
    """WS66i 6-Zone Amplifier (RS-232 / IP control)."""

    name = "WS66i"
    transport = "RS-232 / TCP:8080"

    def set_source(self, zone: int, src: int, zone_name: str, source_name: str):
        payload = f"<{zone:02d}CH{src:02d}"
        return self.command(payload, f"{zone_name} source -> {source_name}")

    def set_volume(self, zone: int, vol_0_38: int, zone_name: str, pct: int):
        payload = f"<{zone:02d}VO{vol_0_38:02d}"
        return self.command(payload, f"{zone_name} volume -> {pct}%")

    def set_mute(self, zone: int, mute: bool, zone_name: str):
        payload = f"<{zone:02d}MU{'01' if mute else '00'}"
        return self.command(payload, f"{zone_name} {'muted' if mute else 'unmuted'}")

    def set_power(self, zone: int, on: bool, zone_name: str):
        payload = f"<{zone:02d}PR{'01' if on else '00'}"
        return self.command(payload, f"{zone_name} power {'ON' if on else 'OFF'}")


class AppleTVDriver(BaseDriver):
    """Apple TV control (pyatv / MRP over the LAN)."""

    name = "AppleTV"
    transport = "pyatv MRP / AirPlay"

    def key(self, source_name: str, key: str):
        payload = f"atvremote --id <mrp-id> {key}"
        return self.command(payload, f"{source_name}: {key}")


class ThermostatDriver(BaseDriver):
    """Ecobee Smart Thermostat (Ecobee REST API v1)."""

    name = "Ecobee"
    transport = "HTTPS REST api.ecobee.com"

    def set(self, field: str, value):
        payload = f'POST /1/thermostat {{"{field}":"{value}"}}'
        return self.command(payload, f"Set {field} = {value}")


class CameraDriver(BaseDriver):
    """Ubiquiti UniFi Protect camera (RTSP / Protect API)."""

    name = "UniFi-Protect"
    transport = "RTSP / Protect WS"

    def snapshot(self, cam_name: str):
        payload = "GET /proxy/protect/api/cameras/<id>/snapshot"
        return self.command(payload, f"{cam_name}: snapshot")


matrix = MatrixDriver()
amp = AmpDriver()
appletv = AppleTVDriver()
thermostat = ThermostatDriver()
camera = CameraDriver()

DEMO_MODE = True
