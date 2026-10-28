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

## 2026-06 Code-review fixes
- Auth: session token now in httpOnly cookie c4_session (SameSite=Lax, Secure on https, 30d), not localStorage; body no longer returns token; Bearer header still accepted for scripts. CSRF guard: cookie-authed non-GET requests need Origin in CORS_ORIGINS or same hostname. CORS allow_credentials=True with explicit CORS_ORIGINS (.env: preview URL, http://192.168.0.10:3000, localhost:3000). Frontend: axios withCredentials, SystemContext.authed drives unlock.
- ping subprocess only accepts literal IPs. exec() finding was a false positive (create_subprocess_exec).
- SSL verify=False kept for Protect/Linkplay self-signed certs (user choice).
- Hook deps fixed (Automations, Scenes, Security, PinLock, SettingsDrawer, SetupWizard); stable keys (PresetBuilder uid, PinLock, DriverDrawer, Automations); empty catches now warn/toast. Big refactors skipped by user choice.

## 2026-06 Rename
- App title, PWA name, lock screen, Home header and top bar renamed to "Smith Apartment" (server.py default property_name, index.html, manifest.json; preview DB updated).

## 2026-06 Windows install + network-independent panel
- Added backend/requirements-windows.txt (18 direct deps; resolves to 66 cp312 win wheels). Guides use py -3.12 venv + this file.
- Frontend BACKEND falls back to window.location.hostname:8001 when REACT_APP_BACKEND_URL unset (no frontend .env on mini-PC).
- Backend CORS allow_origin_regex + CSRF accept private-LAN/Tailscale origins (LAN_ORIGIN_RE). CORS_ORIGINS=http://localhost:3000 on mini-PC.
- User staging mini-PC at home (192.168.1.243) before moving to apartment (192.168.0.x). Mini-PC: Python 3.12.10, Node 24, Yarn 1.22, ffmpeg 9.0.2 essentials, MongoDB reinstalled & running, Git reinstalled, repo newlogical/c4c2 cloned to C:\apartment-controller, backend deps installed.
- Next: start backend, yarn install/build, serve; optional remote testing via WiFiman Teleport.

## 2026-10 On-site commissioning (apartment)
- Mini-PC moved to apartment; backend + built panel (npx serve) running. Node reinstalled as portable zip at C:\nodejs (MSI kept failing 1603).
- USER-CONFIRMED: all 4 Sony TVs work LIVE (PSK + IP control). Next: matrix, amp, Apple TVs, Ecobee, camera.
- Auto-start service not built yet (user must start backend + serve manually after reboot).
- Matrix: MXT40 has NO Telnet. Captured web GUI: POST http://<ip>/output.set<ms> body "#video_d outN matrix=I", Content-Type "charset=UTF-8", Isajax: yes, Cookie sx_login_name/sx_login_pwd = urlencoded base64(user/pass). MatrixDriver now uses this (port 80); config port 23 auto-migrated to 80; test = GET /index.html. Verified against a fake server (byte-identical). Awaiting user live test.
- USER-CONFIRMED: J-Tech matrix switching works LIVE via HTTP driver. Next: Identify outputs, WS66i amp, Apple TVs, Ecobee, camera.

## 2026-10 Listen v2 rework (client spec "Audio, TV Controls, Party Mode & Shortcuts")
- Nav: Listen (landing) / Shortcuts / Thermostat / Settings. Removed from UI: Home, Watch, Security/camera/PTZ/person alerts, Apple TV remotes+pairing, J-Tech matrix + identify, Scenes/presets/automations, TuneIn/Spotify/stream panel, voice-scene section, saver camera mode.
- backend/listen.py (router /api/listen*, /api/shortcuts*): Mongo `listen` doc (rooms layout, status, party) + `shortcuts` collection. LIVE amp writes: one pyws66i session per batch under a lock, confirmed by zone_status read-back; failure => 424, party reconciled to confirmed rooms. DEMO only when amp toggle is DEMO.
- Room map: Living Z1 (TV=1, Mobile=3), Office Z2 (TV=5, Mobile=6), Master Z3 (TV=2, Mobile=4), Bathroom Z4 (Mobile=6, LR TV=1, Office TV=5, Master TV=2); Z5/Z6 hidden. Party sources 6/1/5/2. Admin-editable in Settings → Rooms & sources.
- Startup migration listen_v2_migration deleted old scenes/automations; seeds 5 default shortcuts once (seed_shortcuts_v1).
- display_power no longer touches matrix or amp. Health/checklist drop matrix, Apple TVs, cameras/NVR.
- Tested: iteration_23 (15/15 backend pytest incl. LIVE fake-amp; frontend ~all flows). Fixed after: party false-state on 424, volume readout revert, party label in room header, reorder validation, default auto-fix in Rooms editor.
- Leftover (dead) backend endpoints for matrix/appletv/camera remain unused.

## 2026-10 iOS wrapper
- /app/ios-app: Capacitor 8.5.3 shell (appId com.newlogicaltech.smithapartment). www/index.html = first-launch controller-address screen (default 192.168.0.217, saved in localStorage, reachability via image ping to :3000/icon-192.png, then navigates to http://host:3000). scripts/patch-ios.sh sets ATS local/web-content http, NSLocalNetworkUsageDescription, full-screen, hidden status bar, ITSAppUsesNonExemptEncryption=false. assets/ icon+splash for @capacitor/assets. Guide: /app/IOS_APP.md (TestFlight internal testers for iPad + client iPhone). Not yet built on a Mac — unverified on device.

## 2026-10 WiiM integration (Office TV over Bluetooth)
- listen doc gains `wiims` [{id,name,ip,amp_input}] (2 slots, wiim1/wiim2). Sources (room + party) can carry `wiim` + `wiim_mode` (wifi|bluetooth|line-in|optical). Picking such a source first runs linkplay.switch_mode() and confirms via getPlayerStatus mode (41 BT, 40 line-in, 43 optical, else wifi); failure => 424 and the amp is NOT changed.
- Sources are now identified by label (unique per room); room status stores `source_label` so two buttons sharing one amp input highlight correctly. Shortcut room actions store `label` too.
- Bathroom sources have no WiiM link by default => Bathroom never flips the WiiM (user default).
- Settings → Rooms & sources: WiiM rows (name/IP/wired input/Check) + "Also switch WiiM → mode" per source. GET /api/listen/wiim/{id}/status.
- Sony TV Bluetooth output can't be commanded (no Sony API) — relies on TV auto-reconnect; UI hint shown.
- Fakes for live tests: /app/backend/tests/fakes/fakeamp.py (WS66i telnet :8080), fakewiim.py (LinkPlay HTTP :8098, arg "stuck"). Verified end-to-end; 15/15 iter23 regression pass. Not yet tested on real WiiM Mini.
- 2026-10 layout v2 (user-confirmed wiring): Office WiiM (wiim1) on input 5: Office TV=5 (WiiM→Bluetooth), Office Mobile=5 (WiiM→Wi-Fi). Bathroom WiiM (wiim2) on 6: Bathroom Mobile=6 (WiiM→Wi-Fi). Party "Mobile Device from Living Room"=3 (default party input 3), party "Office TV"=5 (WiiM→BT). No Bathroom Bluetooth. Startup migrate_layout_v2 (meta listen_layout_v2_wiim) applies this only where rooms/party sources still equal the v1 defaults; Music Everywhere shortcut party input 6→3. Shortcuts skip a source the room no longer offers. iter23 tests updated; 15/15 pass.
- 2026-10 Camera re-added (user request): bottom-nav Camera tab (Listen/Shortcuts/Camera/Thermostat/Settings). CameraTab.jsx = Front Entry live HLS (restored CameraPlayer.jsx) + full screen + PtzControls.jsx (presets, patrol, experimental arrows/zoom) + "View recordings" → unifi-protect:// (toast if app not installed). Settings camera card restored (RTSPS, Protect API key, preset names, local user/pass) without person webhook. Health shows NVR + cam again; checklist cam_stream/cam_apikey/ptz_presets restored. Security arm/person alerts stay removed. Backend camera/PTZ endpoints were never deleted.

## 2026-06 — Camera "View recordings" in iOS app
- CameraTab: inside the Capacitor iOS app uses AppLauncher (canOpenUrl unifi-protect:// → open Protect, else App Store id1392492235). Browser/Home Screen: tries scheme, falls back to App Store after 1.8s.
- ios-app: added @capacitor/app-launcher 8.0.1; patch-ios.sh adds LSApplicationQueriesSchemes [unifi-protect]. IOS_APP.md update line now includes npm install.
- Verified with mocked Capacitor bridge in preview (both paths). NOT yet tested on a real iPad/iPhone build.

## 2026-06 — Auto-start, Camera snapshot, WiiM now playing (iteration_24: all pass)
- windows/install-autostart.ps1 (Admin, re-run after updates): two Task Scheduler tasks "Smith Apartment Backend/Panel", AtStartup +20s, SYSTEM, restart loop in start-backend.cmd / start-panel.cmd, logs in /logs, PATH + serve saved in windows/path.cmd (gitignored). remove-autostart.ps1 turns it off. .gitattributes forces CRLF for .cmd/.ps1. Static-reviewed only, NOT run on Windows.
- Camera snapshot (CameraTab SnapshotButton + lib/snapshot.js): canvas capture of live <video>, date/time stamp; iOS app → @capacitor/filesystem + @capacitor/share; browser → Web Share files → download fallback. Stock poster used only in DEMO. Real-camera frame capture NOT verified (headless can't decode demo stream).
- WiiM now playing: GET /api/listen/wiim/{id}/status (demo tracks when amp not LIVE), POST /api/listen/wiim/{id}/play-pause. Shown on active Wi-Fi WiiM Mobile Device buttons (Office, Bathroom), polled every 5s. Real WiiM NOT verified.

## 2026-06 — Power-cut / restart banner
- server.py record_reboot() on startup: if OS uptime < 10 min (Windows GetTickCount64, Linux /proc/uptime) store db.meta last_reboot {boot_at, back_online_at}; same boot (backend crash-loop) not re-recorded. /api/alerts returns "reboot" for 24h.
- frontend RestartBanner.jsx above every tab, polls /alerts every 60s, hides itself after 24h (no dismiss, per user). Self-tested (logic script + screenshots 390/1920). Not yet seen after a real mini-PC reboot.

## 2026-06 — Sony TVs kept on ARC
- listen.prepare_source(): when a source on amp input 1 (tv_living) or 2 (tv_master) is picked (room, Bathroom TV sources, Party source, shortcuts, Restore Defaults), a background task runs ensure_arc(): Bravia audio v1.1 getSoundSettings outputTerminal → setSoundSettings audioSystem → confirm; 4 tries 4s apart. Office TV (input 5, Bluetooth to WiiM) and Guest TV excluded. Mapping in listen doc `arc_inputs` (no UI yet).
- Failures never block the room; stored in db.meta arc_status and shown as amber warnings at top of Device Health (/api/health/devices arc_warnings). Cleared when a later attempt succeeds.
- Tested: backend/tests/test_arc.py (fake Bravia, 4 passed), iter23/24 regression 24 passed, health warning screenshot. NOT yet verified on real Sony TVs. (test_iter11_sony.py is stale: expects token in login body from pre-cookie auth.)

## 2026-06 — TV Sound Check (Device Health)
- POST /api/listen/tv-sound-check: reads every Sony TV's outputTerminal in parallel; ARC TVs (arc_inputs values: living, master) are switched back via ensure_arc(tries=1) and arc_status/warnings updated; Office/Guest only read. Demo: simulated, no output shown.
- frontend TvSoundCheck.jsx card at top of Device Health (Check button, per-TV status: On ARC / Switched to ARC / Checked / Couldn't set ARC / Not answering). Tested: test_arc.py 5 passed with fake Bravia + demo screenshot. NOT yet run against real TVs.

## 2026-06 — iOS app moved into frontend + Codemagic/TestFlight
- Removed /app/ios-app. Capacitor 8.5.3 now in frontend: capacitor.config.json (appId com.newlogicaltech.smithapartment kept from earlier scaffold; webDir ios-shell = first-launch connect screen that opens the live panel at http://<mini-PC>:3000, so cookie auth/API unchanged), ios/ Xcode project (SPM) generated + committed, icons/splash generated from frontend/assets, scripts/patch_ios_plist.py (ATS local, local network, all orientations iPhone+iPad, Photos add, unifi-protect query, encryption=false). Runtime deps @capacitor/core/ios/app-launcher/filesystem/share in frontend package.json; CLI run via npx (needs Node 22) so web/Docker builds unaffected.
- Safe areas: utilities safe-top/bottom/x/all in index.css (env() = 0 on web → no visual change); applied to App shell, TopBar, PinLock, drawers, full-screen panels, SetupWizard, camera fullscreen. Native-only Settings button "Change controller address" → capacitor://localhost/?change=1.
- /codemagic.yaml workflow ios-testflight (mac_mini_m2, working_directory frontend, integration "SmithAppStoreConnect", auto build number, submit_to_testflight). APP_STORE_APPLE_ID placeholder 0000000000 — user must set. NOT yet built on Codemagic; not device-tested.

## 2026-06 — Outside access (port forwarding + security) — iteration_25 pass + fixes
- User choice: port forward with security; own domain; password + TOTP; separate logins (owner, client); Settings allowed remotely.
- windows/Caddyfile + install-remote-access.ps1 (-Domain -Email; downloads Caddy, firewall 80/443, task "Smith Apartment Gateway", auto Let's Encrypt) + start-gateway.cmd + remove-remote-access.ps1. Caddy sets X-Smith-Remote: 1, blocks webhooks/voice/spotify callback/demo/setup-guide. Only 80/443 forwarded. Validated with Caddy v2.10.2 locally (not on Windows).
- backend/remote_auth.py: is_remote = header present (stricter only); db.remote_users (bcrypt, TOTP enrollment at first sign-in via QR, replay protection, 5 fails/IP+user → 15 min lock); remote session pin_ok → PIN required after sign-in; lock keeps sign-in; 5 wrong remote PINs end that device's sign-in (LAN PIN counter untouched); password change/2FA reset/delete revoke sessions; /api/remote/logout works before PIN.
- Frontend: RemoteLogin.jsx, LockGate in App.js, Settings "Outside access" card (RemoteAccessSettings.jsx), PinLock hides setup-guide QR remotely, api.js same-origin API when served on standard port, iOS shell accepts a domain (https). Checklist + Settings guide text updated. REMOTE_ACCESS.md walkthrough.
- Tests: backend/tests/test_remote_access.py (5) + test_iter25_remote_ext.py (4) pass. NOT yet set up on the real router/domain.
- Stale tests to ignore: test_iter11_sony.py (token in body), test_iter22 preset_crud_order (removed music presets).

## 2026-06 — Renamed to "Casa Vestry"
- All visible names (panel, title, manifest, iOS display name, ios-shell, guides, Windows task names, TOTP issuer) → Casa Vestry. Bundle ID → com.newlogicaltech.casavestry. Codemagic integration name → CasaVestryAppStoreConnect.
- get_state migrates stored property_name "Smith Apartment"/"Riverside Apartment" → "Casa Vestry". Windows install/remove scripts also remove the old "Smith Apartment *" tasks/firewall rule.
- Internal identifiers unchanged on purpose: X-Smith-Remote header, SMITH_* env vars (invisible).
- 2026-06: codemagic.yaml APP_STORE_APPLE_ID = 6827836221 (Casa Vestry, App Store Connect). Distribution: TestFlight (user has no iPad yet).
- 2026-06: First successful Codemagic build #4 (commit 8ef0bc4) — signed App.ipa uploaded to App Store Connect. Fix needed: App Store provisioning profile 'Casa Vestry App Store' created manually at Apple and fetched into Codemagic (casavestry_profile). Next: TestFlight internal testing install on user's iPhone; not yet confirmed on device.
- 2026-06: User ran mini-PC update: git pull, pip (pyotp), yarn install, yarn build, install-autostart.ps1 → OK Casa Vestry Backend + Panel (auto-start now live on mini-PC; ffmpeg found). Reboot test + device checks pending.
- 2026-06: Camera 'Stream unavailable' on real G6 PTZ: player requested HLS before ffmpeg wrote the first playlist and gave up. Fix: backend _live_stream waits up to 15s for index.m3u8 (returns readable error with ffmpeg log tail, stream link redacted; logs/ffmpeg-<cam>.log), clears stale segments, dropped append_list; CameraPlayer retries 4x/3s and shows the error text (camera-stream-error). Verified locally with mediamtx RTSP test source (playlist in 3s) + error paths. Awaiting user re-test on mini-PC; arrows/zoom on real camera not yet confirmed.
- 2026-06: Real camera error 'Error opening input: I/O error' on rtsps://UNVR:7441 (Windows ffmpeg + Protect RTSPS). Added automatic fallback to Protect's plain LAN RTSP rtsp://<nvr>:7447/<token> (_plain_rtsp, cached in _ffmpeg_urls). Verified with mediamtx on 7447. Awaiting user re-test.
- 2026-06: 'View recordings' did nothing in TestFlight app (native plugin calls from the remote mini-PC page apparently never answer). Fix: panel detects app via ?casaapp=1 (set by ios-shell panelUrl, kept in sessionStorage; lib/nativeApp.js) and hands off to capacitor://localhost/?open-protect=1; ios-shell (local origin) calls AppLauncher (Protect or App Store) then location.replace back to panel. Change-controller button uses same helper. Snapshot native path now times out after 2.5s → Web Share fallback. Needs new Codemagic build + TestFlight update + mini-PC panel rebuild. NOT yet verified on device.
- 2026-06: User reports View recordings 'just reboots the same app' — consistent with phone still on build 1 (old shell ignores ?open-protect=1). Shell now shows the AppLauncher error for 5s instead of silently returning, plus 'App screens v3' marker on the Connecting screen to identify new builds.
- 2026-06: Device error showed window.Capacitor.registerPlugin undefined in ios-shell (plain HTML, no @capacitor/core bundle). Shell now calls Capacitor.nativePromise('AppLauncher', ...) (confirmed in native-bridge.js), with Plugins/registerPlugin fallbacks. Marker bumped to 'App screens v4'. Needs new Codemagic/TestFlight build.
- 2026-06: WiiM Check said 'Set this WiiM's IP address and save first' — the IP boxes were empty (grey 192.168.0.x is placeholder) and Rooms has its own 'Save rooms & sources' button. Check now tests the typed IP directly (?ip=), validates format, and its toast reminds to save. Real WiiM IPs still not entered.
- 2026-06: ROOT CAUSE WiiM IPs 'not saving': RoomsSettings re-copied layout from ListenContext on every 10s status refresh, wiping unsaved typing. Now loads once (useRef). Same guard added to SettingsDrawer config (loads when drawer opens only). Verified in preview: typed IP survives 12s, saves, persists after reload.
