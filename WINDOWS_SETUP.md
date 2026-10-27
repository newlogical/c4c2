# Running the Apartment Controller on a Windows 11 Mini‑PC

Tailored for: **Windows 11 host**, host LAN IP **`192.168.0.10`**, accessed from an **iPad on the same Wi‑Fi**.

> Why native (not Docker) on Windows? This app powers your TVs with **Wake‑on‑LAN** and talks to the
> matrix/amp/cameras directly on your LAN. Docker Desktop on Windows isolates the network and breaks
> WOL/broadcast. Running the app **natively on Windows** gives it full LAN access.
>
> If you'd rather have a hands‑off appliance, install **Ubuntu** on the mini‑PC instead and use
> `docker compose up -d --build` (see `SELF_HOST.md`). That path "just works" with the shipped Docker files.

---

## 0. One‑time: make the mini‑PC a stable server

1. **Give it a fixed IP.** In your router (UniFi Dream Machine → Client Devices → the mini‑PC → Fixed IP)
   reserve **`192.168.0.10`** so it never changes. Use **wired Ethernet** on the same VLAN/subnet as the
   matrix, amp, Apple TVs, Ecobee and UniFi.
2. **Never sleep.** Windows Settings → System → Power → Screen and sleep → set **Sleep = Never** (both).
3. **Allow it through the firewall.** We'll open ports 3000 and 8001 in Step 5.

---

## 1. Install the prerequisites (one time)

Download and install these on the mini‑PC (accept defaults, and where offered tick **"Add to PATH"**):

| Software | Link | Notes |
|---|---|---|
| **Git for Windows** | https://git-scm.com/download/win | to download the code + get updates |
| **Python 3.11** | https://www.python.org/downloads/ | ✅ tick **"Add python.exe to PATH"** on the first screen |
| **Node.js 20 LTS** | https://nodejs.org/en/download | includes npm |
| **MongoDB Community Server** | https://www.mongodb.com/try/download/community | choose "Install as a Service" (starts automatically) |
| **ffmpeg** | https://www.gyan.dev/ffmpeg/builds/ (get "release full") | unzip to `C:\ffmpeg`, then add `C:\ffmpeg\bin` to PATH (needed for live cameras) |

After installing, enable Yarn (open **PowerShell** and run):
```powershell
corepack enable
corepack prepare yarn@stable --activate
```

Verify everything is on PATH (close and reopen PowerShell first):
```powershell
git --version; python --version; node --version; yarn --version; ffmpeg -version
```
Each should print a version. If one says "not recognized", re‑run its installer and ensure "Add to PATH".

---

## 2. Get the code onto the mini‑PC

**Recommended — via GitHub (lets you pull updates later):**
1. In the Emergent chat, click **"Save to GitHub"** to push this project to your GitHub account.
2. On the mini‑PC, open PowerShell and run (replace with YOUR repo URL):
   ```powershell
   cd C:\
   git clone https://github.com/<your-username>/<your-repo>.git apartment-controller
   cd apartment-controller
   ```

**Alternative — ZIP:** download the project as a ZIP, extract it to `C:\apartment-controller`.

From here we assume the project lives at **`C:\apartment-controller`** (contains `backend\` and `frontend\`).

---

## 3. Set up the BACKEND (API server)

```powershell
cd C:\apartment-controller\backend

# create an isolated Python 3.12 environment (newer Pythons lack prebuilt wheels)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version   # must say 3.12.x

# install dependencies (Windows-specific list; requirements.txt is for the cloud/Linux build)
python -m pip install --upgrade pip
pip install -r requirements-windows.txt
```

Create the backend config file **`C:\apartment-controller\backend\.env`** with this content
(use Notepad; File → Save As → set "Save as type: All Files" so it isn't `.env.txt`):
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=c4clone
CORS_ORIGINS=http://localhost:3000
DEFAULT_PIN=1234
```

Start the backend:
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn server:app --host 0.0.0.0 --port 8001
```
Leave this window open. Test it from the same PC in a browser: `http://localhost:8001/api/` should respond.

---

## 4. Set up the FRONTEND (the UI)

Open a **new** PowerShell window:
```powershell
cd C:\apartment-controller\frontend
yarn install
```

**Do not create a `frontend\.env`.** The panel automatically talks to port 8001 on whichever PC served it,
so the same build works at home, at the apartment, and over VPN — no IP to edit, no rebuild after moving.
Any private-LAN (192.168.x / 10.x / 172.16–31.x) or Tailscale (100.64–127.x) address is accepted by the backend.

Build it and serve it:
```powershell
yarn build
npx serve -s build -l 3000
```
Leave this window open too. Test on the mini‑PC: `http://localhost:3000`.

---

## 5. Open the Windows Firewall (so the iPad can connect)

In an **Administrator** PowerShell (right‑click → Run as administrator):
```powershell
New-NetFirewallRule -DisplayName "Apartment UI 3000"  -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "Apartment API 8001" -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow
```

---

## 6. Open it on the iPad 🎉

On the iPad (same Wi‑Fi), open Safari and go to:
```
http://192.168.0.10:3000
```
Enter the PIN (default **`1234`** — change it later in Settings).

**Make it feel like a native app:** in Safari tap the **Share** icon → **Add to Home Screen**. Launch it
from the home‑screen icon and it opens full‑screen with no browser bars. In iPad Settings → Display &
Brightness → Auto‑Lock → **Never**, so a wall‑mounted iPad stays on.

---

## 7. Turn your real hardware ON (LIVE mode)

Everything runs in **demo/simulation** until you flip each device to LIVE. In the app: **Settings (gear,
top‑right) → On‑site commissioning guide**. For each device toggle **LIVE**, enter its address,
tap **Test connection**, then **Save**. Full per‑device field details are in `SELF_HOST.md` §4, summarised:

- **JTECH‑MXT40 matrix** — enable Telnet (port 23) in its web UI → enter its IP + port 23.
- **WS66i amp** — pre-mapped to `192.168.0.43` (streaming modules .213 / .224). Reserve these in UniFi, then map each source to its physical input 1‑6.
- **Sony Bravia TVs** — IPs/MACs are pre-mapped (Living .165, Office .177, Master .78, Guest .253).
  On each TV: Settings → Network → Home network setup → **IP control** → Authentication *Normal and
  Pre-Shared Key*, set a **PSK**, and turn **Remote start ON**. In the app enter each TV's PSK + HDMI port.
- **Apple TVs** — pre-mapped (ATV1 .145, ATV2 .181, ATV3 .249, ATV4 .35). Settings → Apple TVs → LIVE → tap **Pair this Apple TV** on each and type the PIN shown on the TV (twice: Companion, then AirPlay).
- **G6 PTZ** — paste the RTSPS link, a Protect API key (presets/patrol) and optionally a local Protect user (experimental arrows/zoom). See the printable guide §8.6.
- **Ecobee** — local HomeKit: confirm IP `192.168.0.222`, enter the 8-digit HomeKit code (thermostat Menu → Settings → HomeKit) and tap **Pair thermostat**. Allow Python through Windows Firewall on **Private** networks so mDNS (UDP 5353) discovery works. Don't add the thermostat to Apple Home.
- **UniFi cameras** — enable RTSP in UniFi Protect, paste each camera's `rtsp://...` URL (ffmpeg transcodes to HLS).

---

## 8. Make it start automatically on boot (recommended)

One command sets this up. Afterwards the backend and panel start by themselves at every power-on —
**even if nobody signs into Windows** — and restart on their own if they ever crash.

1. Close any backend/panel PowerShell windows you have open.
2. Right-click **Start** → **Terminal (Admin)** / **Windows PowerShell (Admin)**, then:
```powershell
cd C:\apartment-controller
powershell -ExecutionPolicy Bypass -File .\windows\install-autostart.ps1
```
3. It checks your setup, starts both, and prints **OK** for each. Restart the mini-PC once to confirm
   the panel comes back without signing in.

**After an update** (`git pull`, plus `yarn build` in `frontend` if the panel changed): run the same
command again — it restarts both with the new code.

- Logs: `C:\apartment-controller\logs\backend.log` and `panel.log`
- Task Scheduler → *Task Scheduler Library* shows "Smith Apartment Backend" / "Smith Apartment Panel".
- Turn auto-start off: `powershell -ExecutionPolicy Bypass -File .\windows\remove-autostart.ps1`
- If you install ffmpeg/Node somewhere new later, re-run the install command so the tasks see it.

---

## 9. Remote access from outside home (later)

Never port‑forward 3000/8001 to the internet. Use a VPN:
- **Tailscale** (easiest): install on the mini‑PC and on the iPad, sign in to both. Then rebuild the
  browse to `http://<tailscale-100.x.y.z-ip>:3000` from anywhere (no rebuild needed).
- **UniFi WireGuard/Teleport**: create a client on the Dream Machine, load it on the iPad, then just use
  the normal LAN IP `http://192.168.0.10:3000`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| iPad can't load `http://192.168.0.10:3000` | Firewall rules (Step 5) not added, or iPad on a different Wi‑Fi/VLAN. |
| UI loads but everything errors / no data | Backend window closed, or port 8001 blocked by the firewall. Make sure there is NO `frontend\.env` (delete it and `yarn build` again if one exists). |
| "not recognized" for python/node/yarn/ffmpeg | Re‑run installer with "Add to PATH", reopen PowerShell. |
| Camera shows "Stream unavailable" | ffmpeg not on PATH, or wrong RTSP URL / camera RTSP disabled. |
| TV won't power on | Wake‑on‑LAN needs the correct **MAC** + "Network standby" enabled on the TV; host on same L2 network. |
| Changed IP but iPad still broken | You must re‑run `yarn build` after editing `frontend\.env` (the IP is baked in at build time). |
