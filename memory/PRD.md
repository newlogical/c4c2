# PRD — Control4-Style Apartment Home Controller (Clone)

## Original Problem Statement
Build a clone of a Control4 controller for an apartment. Single interface to replace multiple
remotes/apps. Rack already wired (CAT6 to each TV, speaker wire to each zone). Modeled equipment:
J-Tech JTECH-MXT40 4x4 HDMI/HDBaseT matrix, WS66i 6-zone amplifier, UniFi Dream Machine + UniFi
camera, 4 Apple TVs (video sources), Ecobee thermostat.
Rooms: Living Room (TV+audio), Office (TV+audio), Master Bedroom (TV+audio), Guest Bedroom (TV only),
Bathroom (audio only).

## User Choices
- Demo/simulation now, structured for real integration later.
- Simple PIN lock (PIN 1234) + demo bypass.
- Include UniFi camera live tile.
- Full Ecobee control (targets, mode, fan, humidity/outdoor readouts).
- Dark, modern smart-home aesthetic, native-app feel.

## Architecture
- Frontend: React SPA. PIN gate + 6 tabs (Home, Watch, Listen, Climate, Security, Scenes),
  bottom dock nav, driver command-log drawer. framer-motion, lucide-react, sonner, Tailwind.
  State via SystemContext -> axios -> backend.
- Backend: FastAPI. Single system-state document in MongoDB (collection `system`, key `main`),
  seeded from `default_state()`. All routes `/api`-prefixed.
- `drivers.py`: hardware driver abstraction (MatrixDriver/AmpDriver/AppleTVDriver/ThermostatDriver/
  CameraDriver). DEMO_MODE=True formats + logs the real protocol commands (JTECH ASCII, WS66i RS232,
  Ecobee REST, pyatv, UniFi RTSP) into `command_log` instead of sending. To go live: implement each
  driver's transport and set DEMO_MODE=False. **All device control is MOCKED (simulation).**

## Self-hosting note (answer to user's hardware question)
Runs on any always-on box on the apartment LAN — a Raspberry Pi 4/5 or an Intel mini-PC (NUC) is
plenty. It must be on the same VLAN/subnet as the matrix, amp, Apple TVs, Ecobee and UniFi so the
drivers can reach them (Telnet/RS232/HTTP/RTSP).

## Implemented (2026-06)
- PIN lock screen (keypad, error shake, demo bypass).
- Home dashboard: hero, stat cards, quick scenes, room rows.
- Watch: 4x4 matrix router grid, per-display source buttons, broadcast-to-all, power toggle,
  Apple TV virtual remote modal.
- Listen: 4 audio zones (source/volume/mute/power) + whole-home group sync.
- Climate: circular dial, heat/cool/auto/off, conditional target steppers, fan modes, readouts.
- Security: UniFi camera live tile, snapshot, fullscreen modal, motion/armed status.
- Scenes: All Off, Good Night, Movie Night, Whole-Home Audio + system reset.
- Driver command-log drawer showing live simulated protocol traffic.
- MongoDB state persistence across reloads. Tested: 20/20 backend, all frontend flows pass.

## Backlog / Remaining
- P1: Real driver transports (JTECH Telnet, WS66i RS232/IP, Ecobee OAuth REST, pyatv, UniFi Protect).
- P1: Live camera RTSP/WebRTC stream (currently static tile).
- P2: Lighting/shades zones, multi-property, PIN rate-limiting, per-user profiles.
- P2: Schedules/automations, energy dashboard.
