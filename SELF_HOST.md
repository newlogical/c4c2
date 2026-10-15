# Self‑Hosting & On‑Site Commissioning Guide

This app is a **Control4‑style controller** for your apartment. In the cloud preview every device is
**simulated**. To control the real rack you run it on a small always‑on computer that sits on the
**same LAN** as your equipment, then flip each device to **LIVE** in **Settings** and enter its address.

---

## 1. Hardware to host it on

Any of these on the apartment network works:

| Option | Notes |
|---|---|
| **Raspberry Pi 4 (4 GB) or Pi 5** | Cheapest, silent, plenty for this app. Use a good SD/SSD. |
| **Intel mini‑PC / NUC** | Most headroom; nice if you later add camera transcoding. |
| **Any Linux/macOS box already on the rack** | Fine as long as it stays on 24/7. |

Requirements: wired Ethernet on the **same subnet/VLAN** as the matrix, amp, Apple TVs, Ecobee and
UniFi. Wake‑on‑LAN (TV power‑on) and the amp/matrix control need the host on that L2 network.

---

## 2. Run it — Docker (recommended)

Install Docker + Docker Compose, then from the project root:

```bash
# 1. Edit docker-compose.yml -> set REACT_APP_BACKEND_URL to THIS host's LAN IP, e.g.
#    args: REACT_APP_BACKEND_URL=http://192.168.1.10:8001
docker compose up -d --build
```

- UI: `http://<host-ip>:3000`
- API: `http://<host-ip>:8001/api`

The **backend runs with host networking** so Wake‑on‑LAN broadcasts and Telnet/RS‑232‑over‑IP reach
your devices. MongoDB data persists in the `mongo_data` volume.

### Run on a wall tablet
Open `http://<host-ip>:3000` in the tablet browser and "Add to Home Screen" for a full‑screen,
app‑like experience. Set the tablet to never sleep.

---

## 3. Run it — manual (no Docker)

```bash
# MongoDB (any 6/7 instance reachable from the host)
# Backend
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional live extras: pyatv (Apple TV), ffmpeg (camera) — install on the host:
#   pip install pyatv       &&   sudo apt-get install -y ffmpeg
export MONGO_URL="mongodb://localhost:27017"
export DB_NAME="c4clone"
export CORS_ORIGINS="http://192.168.0.10:3000"
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend (new terminal)
cd frontend
yarn install
echo "REACT_APP_BACKEND_URL=http://<host-ip>:8001" > .env
yarn build && npx serve -s build -l 3000
```

---

## 4. Prepare each device, then enable LIVE

Open **Settings** (gear icon, top‑right) → expand **On‑site commissioning guide**. For each device,
toggle **LIVE**, fill in the fields, tap **Test connection**, then **Save**.

### JTECH‑MXT40 matrix — video routing
- In the matrix web UI, enable **Telnet** (TCP **23**).
- Settings → *JTECH‑MXT40 Matrix* → Host/IP + port `23`.

### WS66i amplifier — audio zones
- Set the rear network switch to **ETHERNET** and give it a static IP/DHCP reservation.
- Settings → *WS66i Amplifier* → Host/IP (pre-mapped `192.168.0.43`; streaming modules `192.168.0.213`, `192.168.0.224`).
- **Source → input map**: for each logical source (Apple TV 1‑4, Spotify, AirPlay, TV Audio) enter the
  **physical WS66i input number (1‑6)** it's actually wired to. (Defaults 1‑6; fix to match your wiring.)

### Ecobee — thermostat (local HomeKit, no cloud)
- Ecobee closed its developer API to new accounts (2024), so the app pairs over HomeKit (HAP/IP) on the LAN.
- Settings → *Ecobee Thermostat* → LIVE → confirm LAN IP → enter the HomeKit setup code (Menu → Settings → HomeKit) → **Pair thermostat**.
- One HomeKit controller at a time: keep the thermostat out of Apple Home. mDNS (UDP 5353) must reach the host.

### UniFi Protect — camera
- In UniFi Protect, enable **RTSP** on the camera and copy the stream URL
  (`rtsp://<NVR-IP>:7447/<streamGUID>_0`).
- Settings → *UniFi Protect Camera* → RTSP URL. The backend transcodes it to HLS with **ffmpeg**
  (must be installed on the host). In demo it plays a public test stream.

### Apple TVs — sources / remote
- On the host: `pip install pyatv`, then `atvremote scan` and `atvremote --id <id> pair` (Companion) for
  each unit; save the credentials.
- Settings → *Apple TVs* → enable LIVE. (Device IDs/credentials are provisioned on the host.)

### Sony Bravia TVs (KD-49X7000E) — power / volume / input
- Mapped TVs (from UniFi): Living Room `192.168.0.165`, Office `192.168.0.177`,
  Master Bedroom `192.168.0.78`, Guest Room `192.168.0.253` — reserve these IPs in UniFi.
- On each TV: **Settings → Network → Home network setup → IP control**
  - **Authentication = Normal and Pre-Shared Key**, then set a **Pre-Shared Key** (e.g. a 4-digit code).
  - **Remote start = ON** (lets the TV wake from the network).
  - Turn **off** private/random Wi-Fi MAC so Wake-on-LAN and IP reservations stay valid.
  - (Menu wording varies slightly by firmware.)
- Settings → *Sony Bravia TVs* → per TV confirm **IP** + **MAC**, enter the **PSK** and the **HDMI port**
  its HDBaseT receiver feeds.
- Power-off / input / volume use the Bravia REST API (`X-Auth-PSK`); remote keys use IRCC;
  **power-on sends Wake-on-LAN** plus `setPowerStatus`. Wired Ethernet is the most reliable for wake.

---

## 5. Verify

- Route an Apple TV to a TV (Watch tab) → the display should switch; the **Driver Log** (terminal icon)
  shows the command tagged **sent**.
- Power a TV on → matrix + SonyBravia entries appear.
- Settings → **Device health** (or the pulse icon in the top bar) shows every mapped device online.
- Change an audio zone source → the WS66i command uses the mapped physical input.
- Automations (Scenes tab) run on schedule or on the **Simulate motion** event.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Command log shows **error** | Device unreachable/misconfigured. Check IP, same subnet, device control enabled. |
| TV won't power **on** | Needs the correct **MAC**, **Remote start = ON**, and the host on the same L2 network. Wi-Fi wake is unreliable on Sony — use Ethernet if possible. |
| TV powers on but wrong input | Set the correct HDMI port on that TV's card in *Sony Bravia TVs*. |
| Sony command **error 403/401** | PSK mismatch or IP control authentication not set to *Normal and Pre-Shared Key*. |
| Camera "Stream unavailable" | ffmpeg missing on host, or wrong RTSP URL / camera RTSP disabled. |
| Everything says **simulated** | The device is still in DEMO — toggle it LIVE and Save. |

---

## 7. Security
- Keep this on your LAN. Do **not** port‑forward 8001/3000 to the internet; use a VPN/Tailscale for
  remote access.
- Treat Sony PSKs and HomeKit pairing data as secrets. Change the app **PIN** from the default `1234`
  (in `backend/server.py` `default_state()` → `pin`, or via the database).

---

## 8. Remote access (use the app away from home)

Never expose the app directly to the internet. Tunnel in instead.

### Recommended — Tailscale (free, ~5 min)
1. On the host:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
2. Install the **Tailscale** app on your phone/tablet and sign in with the same account.
3. Note the host's tailnet IP (`tailscale ip -4`, looks like `100.x.y.z`).
4. From anywhere, open `http://100.x.y.z:3000`. Because the backend uses host networking it's reachable
   at `http://100.x.y.z:8001`; if you built the frontend with a LAN IP, rebuild with
   `REACT_APP_BACKEND_URL=http://100.x.y.z:8001` (or use MagicDNS name) so API calls resolve remotely.

### Alternative — WireGuard on the UniFi Dream Machine
- UniFi Network → **VPN → WireGuard/Teleport** → create a client, load it on your phone.
- Connect the VPN, then browse to the host's normal LAN IP (`http://192.168.1.x:3000`).

### Wall tablet inside the apartment
- Just use the LAN IP and "Add to Home Screen"; no VPN needed on‑site.

> Tip: the built‑in **PIN lock** is your last line of defence — change it from `1234` before enabling
> remote access.

