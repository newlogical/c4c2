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
- MACs added (SONY_TV_MACS): Living 1C:D6:BE:B3:FB:1C, Office FA:8A:FD:3F:67:FC, Master FA:D8:24:B4:79:2F, Guest 8E:BF:A2:FC:72:BF. Office/Master/Guest are randomized private MACs -> disable Private MAC on TVs or WoL may fail.
- Ecobee mapped: ip 192.168.0.222, mac 44:61:32:DF:C2:A9, model Smart Thermostat Premium (ECOBEE_LAN in server.py; shown in Settings). Control still via Ecobee cloud API token — IP is reference only.

## 2026-06 Ecobee -> local HomeKit
- Ecobee developer API closed to new accounts (2024). Replaced cloud REST with HomeKit HAP/IP via aiohomekit 4.0.1 (backend/homekit.py, drivers.ThermostatDriver).
- Endpoints: POST/DELETE /api/homekit/pair {code}, POST /api/climate/refresh (ClimateTab polls 60s when live+paired). Pairing data in db.homekit {key:ecobee}; loaded at startup. Setup code NOT stored.
- Settings Ecobee card: IP, MAC, HomeKit code + Pair/Unpair. Token/thermostat_id removed (migration pops).
- Iteration 12: 100% pass (cloud error paths only). Real pairing pending on mini-PC; needs Windows Firewall Private allow for mDNS.
- Stale Samsung/SmartThings sections still in SELF_HOST.md / setup-guide.html 8.5 (cleanup pending).

## 2026-06 Device Health + guide cleanup
- GET /api/health/devices: TCP probe (TVs :80, matrix :port, amp :8080, cameras RTSP host:port) / ping (Ecobee). DeviceHealthPanel.jsx opened from TopBar pulse icon (online/total badge, polls 30s) and Settings card.
- SELF_HOST.md, WINDOWS_SETUP.md, setup-guide.html: Samsung/SmartThings removed; Sony Bravia steps (IP control PSK, Remote start, private MAC off) + IP/MAC table. Iteration 13: 100% pass.
- Note: matrix/amp still default placeholder IPs (192.168.1.1 / .1.50) - user needs real IPs.
- WS66i mapped: host 192.168.0.43 (Soundavo app Manual IP, control TCP 8080). Streaming modules (UniFi "Arylic A50+"): stream_a 192.168.0.213 00:22:6C:22:18:5E, stream_b 192.168.0.224 00:22:6C:1E:6F:39 -> config.amp.streamers, shown in health + Settings. User confirmed they are the WS66i streaming modules. All device IPs reserved in UniFi (user confirmed).
- J-Tech MXT40 mapped: 192.168.0.254 :23, username/password (factory admin/admin) in config.matrix, password masked in /api/state. Driver answers Telnet login prompt only if presented (verified with fake telnet server).
- Apple TVs mapped (config.appletv.devices): atv1 .145 F0:B3:EC:35:5C:41, atv2 .181 F0:B3:EC:3D:63:5E, atv3 .249 58:D3:49:EF:E7:E2, atv4 .35 F0:B3:EC:5E:7B:B9. Driver uses atvremote -s IP + companion/airplay creds (masked). Health checks TCP 7000. Pairing via CLI on mini-PC (in-app pairing not built).
- Cameras: only G6 PTZ (cam_front "Front Entry", 192.168.0.73, 8C:ED:E1:DA:15:4F); demo cams removed by migration. NVR config.nvr 192.168.0.166 74:FA:29:4B:01:30 (health TCP 7441). rtsp_url masked; ffmpeg now accepts rtsps:// and strips ?enableSrtp; camera test probes NVR port. Iteration 14 100%. User could not find RTSPS toggle - gave instructions; link still pending.

## 2026-06 PTZ + in-app Apple TV pairing
- protect.py: official Integration API (X-API-KEY) goto preset/patrol; experimental private /proxy/protect/api/cameras/{id}/move continuous (-1000..1000) via local user login + CSRF, 1.5s dead-man auto-stop. Camera id resolved by MAC.
- Endpoints: GET /api/ptz/presets, POST /api/ptz/goto|patrol|move; upstream errors -> HTTP 424 (502 is eaten by preview proxy). Config camera: protect_api_key, protect_user, protect_password (masked), ptz_presets names.
- PtzControls.jsx on Security tab (Front Entry): presets, patrol toggle, hold-to-move D-pad + zoom.
- Apple TV pairing: POST /api/appletv/{aid}/pair/start {protocol companion|airplay} + /pair/finish {pin}; pyatv 0.18 (protobuf 6.x). AtvPair.jsx in Settings.

## 2026-06 WS66i input map (user confirmed)
- Inputs: 1 Apple TV 1, 2 Apple TV 2, 3 AirPlay 1 (streaming module), 4 AirPlay 2, 5-6 unused. Spotify -> input 3 (assumed; user unsure which module is 3 vs 4). audio_sources = atv1, atv2, airplay, airplay2, spotify (ATV3/4 + TV Audio removed from Listen). One-time migration flag ws66i_wiring_v1.

## 2026-06 Matrix wiring helper
- POST /api/matrix/identify {input,output} raw route; PUT /api/matrix/map {outputs:{tv:n},inputs:{atv:n}} unique 1-4 validation. MatrixWiring.jsx (dropdowns w/ auto-swap) + MatrixIdentify.jsx wizard (step1: flip output n between inputs 1/2, user taps TV that blinks; step2: show input k on Living TV, user picks Apple TV, Test sends Home). Wiring still unconfirmed by user (defaults 1-4).

## 2026-06 First-night checklist + fullscreen remote
- GET /api/checklist (14 items, auto-detect from config/pin hash/device health; manual ids install, ipad_wifi, tv_setup, ptz_presets, remote_access), POST /api/checklist/{id} {done}. FirstNightChecklist.jsx (portal) from Settings card with Go buttons (scroll to settings-* testids / health / guide).
- AppleTVRemote now full-screen via createPortal (framer transform on tab wrapper broke position:fixed -> cut off bottom-right). Scene/Automation modals centered with m-auto instead of translate. Modals inside SettingsDrawer (checklist, MatrixIdentify) portaled to body.
- WS66i zones confirmed by user: 1 Living Room, 2 Office, 3 Master Bedroom, 4 Bathroom (matches defaults; protocol zone ids 11-14). Zones 5-6 unused.

## 2026-06 Presets + Linkplay streaming
- Presets = db.scenes docs with "actions" [{type,target,value}] types tv_power, tv_route, tv_volume, amp_source, amp_volume, amp_power, stream_preset. POST /api/presets, PUT /api/presets/{id}, run via POST /api/scene/{id} (apply_actions; 6s wait after TV WoL before TV volume when live). Seeded once (db.meta flag) "Watch TV in Living Room with Sound" (id preset_living_tv_sound). PresetBuilder.jsx (Scenes: New preset / edit pencil).
- linkplay.py: httpapi.asp (https then http, verify off): getPlayerStatus, getMetaInfo, getPresetInfo, MCUKeyShortClick:N, setPlayerCmd. Endpoints GET /api/stream/status, GET /api/stream/{sid}/presets, POST /api/stream/{sid}/play {preset,zones}, POST /api/stream/{sid}/cmd. streamers stream_a->airplay (input 3), stream_b->airplay2 (input 4) via audio_source (assumed). Demo sim in state.stream_sim. StreamPanel.jsx on Listen (user picks module + rooms each time).

## 2026-06 Pinned presets + Sony remote
- state.pinned_scenes (default [preset_living_tv_sound]); POST /api/scenes/{id}/pin {pinned}; delete unpins. Star on Scenes cards; big pinned buttons at top of Home (pinned-<id>).
- SonyRemote.jsx full-screen (portal): power (WoL via displayPower), input, guide, Netflix, YouTube, D-pad+OK, back/home/options, vol/mute, play/pause, CH+/-, 0-9. IRCC codes added in drivers.SonyBraviaDriver._IRCC. Opens from Watch (open-sony-remote-<id>) and Home room rows (room-remote-<id>).

## 2026-06 TuneIn / Spotify / Pandora
- music.py: TuneIn OPML (Search/Browse/Tune.ashx, follow_redirects) + spotipy auth-code flow (client id/secret in config.spotify, secret masked; token in db.spotify; redirect http://127.0.0.1:8001/api/spotify/callback = public path, state-checked).
- Endpoints: /api/tunein/search|browse/{cat|cNNN|gNN}|saved (CRUD), /api/stream/{sid}/play_station, /api/spotify/status|login|callback|library|link, /api/stream/{sid}/play_spotify. Preset steps tunein_station, spotify_play (+label).
- state.tunein_saved seeded: WFAN direct Audacy url (live.amperwave.net/direct/audacy-wfanamaac-imc; WFAN not on TuneIn), ESPN Radio s25876, FOX Sports Radio s28060, NBC Sports Radio s353779, Bloomberg s165740, CNBC s110052, Bloomberg TV s47135.
- Pandora = Linkplay favourites (no API). UI: StreamPanel sheet tabs Favourites·Pandora / TuneIn (TuneInBrowser.jsx) / Spotify (SpotifyBrowser.jsx); SpotifyCard.jsx in Settings. Client Premium status unknown.

## 2026-06 Game-day / Morning brief / Person + offline alerts
- Seeded once (db.meta seed_music_presets): preset_yankees_wfan (WFAN stream_a, 4 zones airplay @40, pinned), preset_morning_brief (Bloomberg s165740 stream_b, office airplay2 @20) + automation auto_morning_brief weekdays(1-5) 08:00.
- Person: public POST /api/protect/webhook/{config.camera.webhook_token} (Protect Alarm Manager webhook); alerts only when camera.armed; state.person_alert; POST /api/protect/test-person, /api/protect/webhook-token (rotate). GET /api/alerts (light poll). PersonAlert.jsx global modal (polls 4s, live CameraPlayer, auto-close 60s).
- Offline: scheduler job offline_watch every 60s (reload_jobs keeps it); devices live && offline >=180s -> state.offline_alerts; OfflineBanner.jsx on Home (polls 30s, opens Device health).
- Room presets (seed_room_presets): preset_office_tv_sound (tv_office/atv2/audio_office), preset_master_tv_sound (tv_master/atv2/audio_master), preset_bathroom_audio (audio_bathroom->atv2); all pinned to Home. Only atv1/atv2 feed the amp.
