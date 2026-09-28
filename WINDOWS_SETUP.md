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

# create an isolated Python environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# install dependencies
pip install -r requirements.txt
# optional: Apple TV control
pip install pyatv
```

Create the backend config file **`C:\apartment-controller\backend\.env`** with this content
(use Notepad; File → Save As → set "Save as type: All Files" so it isn't `.env.txt`):
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=c4clone
CORS_ORIGINS=*
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

Create the frontend config file **`C:\apartment-controller\frontend\.env`** — this bakes in your mini‑PC's
IP so the iPad can reach the API:
```
REACT_APP_BACKEND_URL=http://192.168.0.10:8001
```

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
- **WS66i amp** — set to Ethernet, give it a fixed IP → enter IP, then map each source to its physical input 1‑6.
- **Samsung TVs** — per TV enter IP + **MAC** + HDMI input #; on the TV enable Network standby (for WOL).
  First LIVE connect, tap **Allow** on the TV. (Optional SmartThings PAT for exact input/volume.)
- **Apple TVs** — in the backend venv run `atvremote scan` then `atvremote --id <id> pair`, save creds; enable LIVE.
- **Ecobee** — paste an access token + thermostat id.
- **UniFi cameras** — enable RTSP in UniFi Protect, paste each camera's `rtsp://...` URL (ffmpeg transcodes to HLS).

---

## 8. Make it start automatically on boot (optional but recommended)

So you never have to touch the mini‑PC after a power cut. Two simple `.bat` files + Task Scheduler:

Create **`C:\apartment-controller\start-backend.bat`**:
```bat
cd /d C:\apartment-controller\backend
call .venv\Scripts\activate.bat
uvicorn server:app --host 0.0.0.0 --port 8001
```

Create **`C:\apartment-controller\start-frontend.bat`**:
```bat
cd /d C:\apartment-controller\frontend
npx serve -s build -l 3000
```

Then in **Task Scheduler** → Create Task (for each .bat): General → "Run whether user is logged on or
not"; Triggers → **At startup**; Actions → Start the .bat. Now both start on boot.

> For a cleaner service install you can use **NSSM** (https://nssm.cc) to run each as a Windows service.

---

## 9. Remote access from outside home (later)

Never port‑forward 3000/8001 to the internet. Use a VPN:
- **Tailscale** (easiest): install on the mini‑PC and on the iPad, sign in to both. Then rebuild the
  frontend with `REACT_APP_BACKEND_URL=http://<tailscale-100.x.y.z-ip>:8001` and browse to it from anywhere.
- **UniFi WireGuard/Teleport**: create a client on the Dream Machine, load it on the iPad, then just use
  the normal LAN IP `http://192.168.0.10:3000`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| iPad can't load `http://192.168.0.10:3000` | Firewall rules (Step 5) not added, or iPad on a different Wi‑Fi/VLAN. |
| UI loads but everything errors / no data | Frontend `.env` IP wrong, or backend window closed. It must read `http://192.168.0.10:8001`. Rebuild frontend after any `.env` change. |
| "not recognized" for python/node/yarn/ffmpeg | Re‑run installer with "Add to PATH", reopen PowerShell. |
| Camera shows "Stream unavailable" | ffmpeg not on PATH, or wrong RTSP URL / camera RTSP disabled. |
| TV won't power on | Wake‑on‑LAN needs the correct **MAC** + "Network standby" enabled on the TV; host on same L2 network. |
| Changed IP but iPad still broken | You must re‑run `yarn build` after editing `frontend\.env` (the IP is baked in at build time). |
