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
### Iteration 1 — MVP
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

### Iteration 2 — Live stream, real drivers, automations (30/30 backend tests)
- Live camera: hls.js player (CameraPlayer). Demo uses public HLS + still-image fallback; self-host
  streams real UniFi Protect RTSP→HLS via a backend ffmpeg proxy (`/api/camera/stream`, `/api/camera/hls/*`).
- Real device drivers: config-driven dispatch in `drivers.py` — each device toggles LIVE with LAN
  settings and dispatches real protocol (JTECH socket Telnet, WS66i pyws66i, Ecobee REST, Apple TV
  atvremote) with automatic simulation fallback; per-command status (simulated/sent/error) in the log.
- Settings drawer: per-device live toggle + connection fields + Test Connection (`PUT /api/config`,
  `POST /api/config/test/{device}`).
- Automations & Schedules: APScheduler cron jobs; create/list/toggle/run/delete; time+weekday
  schedule triggers and motion-event triggers (Security "Simulate motion"). Stored in Mongo
  `automations`. Endpoints under `/api/automations` + `/api/trigger/{event}`.

### Iteration 3 — Samsung TV control
- Per-TV power (Wake-on-LAN on, samsungtvws off), TV volume keys, fixed HDMI input; Settings Samsung TVs card. 10/10 tests.

### Iteration 4 — Amp mapping, SmartThings, commissioning, power-on retry (17/17 tests)
- Amp source→WS66i physical input map (config.amp.input_map) used by zone/group/scene; editable in Settings.
- SmartThings integration: exact HDMI input on power-on + absolute TV volume (config.smartthings PAT + per-TV device id); Settings card + Watch TV volume slider.
- On-site commissioning: SELF_HOST.md + docker-compose.yml + Dockerfiles + in-app collapsible guide.
- TV power-on Wake-on-LAN + HDMI-select retry (4x); live driver dispatch offloaded via asyncio.to_thread.

### Deployment aids (2026-06)
- WINDOWS_SETUP.md: full native-Windows-11 self-host walkthrough (user's mini-PC @ 192.168.0.10, iPad access).
- frontend/public/setup-guide.html: standalone printable (Print/Save-as-PDF) commissioning guide, 13 parts + checklist.
- Settings drawer: "Setup & install guide" link card (data-testid="setup-guide-link") opens /setup-guide.html in new tab.

### Security lock-down (2026-06) — verified iteration_10 (24/24 backend, 100% frontend)
- Session-token auth: `POST /api/auth/pin` (or `/api/auth/demo` in demo mode) issues an opaque `secrets` token stored in `db.sessions` (30-day expiry). `auth_gate` HTTP middleware requires `Authorization: Bearer` on all `/api` routes except public: `/`, `/bootstrap`, `/auth/pin`, `/auth/demo`, `/voice/scene/*`, `/camera/stream*`, `/camera/hls*`.
- `POST /api/auth/logout` revokes token. Frontend: axios interceptor attaches Bearer from `localStorage['c4_token']`, 401 → `c4-unauthorized` event → lock screen. PinLock reads `/api/bootstrap` for name + demo_mode; demo-skip button only shows in demo mode.
- Secret redaction: ecobee/smartthings/tv tokens masked as `"__stored__"` in `/api/state`; `_unmask` on `PUT /config` preserves stored secret (resend mask = keep, ''=clear, new=overwrite).
- SSRF fix: `_ensure_ffmpeg` rejects non-`rtsp://` URLs + `-protocol_whitelist`. Path-traversal fix: `/camera/hls` sanitizes cam_id/filename + confines to HLS_DIR (404 on escape). CORS `allow_credentials=False` (Bearer, not cookies).

### Sony Bravia TV driver + lock-screen QR (2026-06) — verified iteration_11 (100% backend+frontend)
- TVs are Sony KD-49X7000E. Replaced Samsung `samsungtvws` driver with `SonyBraviaDriver` (drivers.py): Bravia REST API `http://<ip>/sony/<service>` with `X-Auth-PSK` header (power `system.setPowerStatus`, input `avContent.setPlayContent extInput:hdmi?port=N`, volume `audio.setAudioVolume`), IRCC-IP SOAP for remote keys (KEY_VOLUP/DOWN/MUTE/etc), Wake-on-LAN for power-on.
- Config: `tv.sets.<id>` now `{ip, mac, hdmi_input, psk}` (psk replaces Samsung token, masked in /state). SmartThings removed entirely (Samsung-only). get_state migrates legacy token→psk and drops smartthings.
- Settings + Setup Wizard cards relabeled "Sony Bravia TVs" (IP/MAC/HDMI/PSK fields); SmartThings card removed. WatchTab volume toast → "Sony Bravia absolute level".
- PIN lock screen shows a QR code (qrcode.react) linking to `/setup-guide.html` ("Scan for the setup guide").

## Backlog / Remaining
- P1: Real-hardware commissioning on-site (self-host on Pi/mini-PC; SELF_HOST.md + WINDOWS_SETUP.md + docker-compose provided). Validate Sony PSK + WoL against the actual KD-49X7000E units.
- P2: Lighting/shades zones, multi-property, PIN rate-limiting, per-user profiles.
- P2: Low-latency camera (WebRTC/go2rtc), energy dashboard, richer automation conditions.

## 2026-06 Sony TV IP mapping
- Mapped from UniFi screenshots (all Sony; ignore UniFi manufacturer labels): Living Room TV 192.168.0.165, Office TV 192.168.0.177, Master Bedroom TV 192.168.0.78, Guest Room TV 192.168.0.253 (renamed from Guest Bedroom TV)
- SONY_TV_IPS in server.py; defaults + migration fills empty IPs; discovery probes these on port 80 (was Samsung 8001)
- MACs not shown in screenshots: still pending (needed for Wake-on-LAN). PSKs pending.
- Next: MACs, PSKs, HDMI ports, mini-PC install, Claude integration (not started)
