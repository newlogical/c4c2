# Casa Vestry — iPhone & iPad app (Capacitor + Codemagic → TestFlight)

The web app is unchanged and keeps working in browsers. The iOS app is a native shell built from the
same `frontend` folder:

- On first launch it asks for the mini-PC address (e.g. `192.168.0.217`), checks it can reach it, then
  opens the live panel from the mini-PC. Login (PIN + secure cookie), camera, every control and all API
  calls work exactly as in Safari, because the app is showing the real panel.
- Next launches reconnect automatically. To switch address: **Settings → Change controller address**.
- The mini-PC must be on and reachable (apartment Wi-Fi, or Teleport/Tailscale when away).
- All orientations on iPhone and iPad; screens respect the notch, rounded corners and home indicator.

## What's in the repo
| Path | Purpose |
|---|---|
| `frontend/capacitor.config.json` | App ID `com.newlogicaltech.casavestry`, name, LAN navigation rules |
| `frontend/ios-shell/index.html` | First-launch "connect to controller" screen |
| `frontend/ios/` | The Xcode project (Swift Package Manager, no CocoaPods) |
| `frontend/assets/` | Source icon + splash (already generated into the Xcode project) |
| `frontend/scripts/patch_ios_plist.py` | iOS permissions: local network, LAN http, orientations, Photos, Protect app |
| `codemagic.yaml` (repo root) | Cloud build → signed IPA → TestFlight |

## 1. One-time: App Store Connect
1. **developer.apple.com → Identifiers → +** → App IDs → App → Bundle ID (explicit)
   `com.newlogicaltech.casavestry`. (Want a different ID? Change it in `frontend/capacitor.config.json`,
   `codemagic.yaml` and the Xcode project, or ask me to.)
2. **appstoreconnect.apple.com → Apps → + New App** → iOS, name *Casa Vestry*, that bundle ID, any SKU.
3. Open the app → **App Information** → copy the **Apple ID** number (e.g. `6740000000`).
4. **Users and Access → Integrations → App Store Connect API → +** → name `Codemagic`, access **App Manager**.
   Download the `.p8` file (only once) and note the **Issuer ID** and **Key ID**.

## 2. One-time: Codemagic
1. Sign in at **codemagic.io** with GitHub and add this repository (it detects `codemagic.yaml`).
2. **Teams → Integrations → Developer Portal → Connect** → upload the `.p8`, enter Issuer ID + Key ID,
   and name it exactly **`CasaVestryAppStoreConnect`**.
3. **Code signing identities → iOS certificates → Generate certificate** (Apple Distribution), then
   **iOS provisioning profiles → Fetch profiles** for the bundle ID (type App Store). Codemagic can create
   both for you through the integration.
4. In `codemagic.yaml`, replace `APP_STORE_APPLE_ID: 0000000000` with the number from step 1.3 and save to
   GitHub. Builds start automatically on every push to `main` (or press **Start new build**).

## 3. Each build
Codemagic installs packages, syncs the iOS project, signs it, picks the next build number, and uploads to
TestFlight. After Apple's processing (~10–30 min), open **TestFlight** on the iPad/iPhone and install.
Add testers in App Store Connect → TestFlight → Internal Testing.

## Building on the Mac mini instead (optional)
```bash
cd frontend
yarn install
yarn ios:sync      # needs Node 22+
yarn ios:open      # opens Xcode → pick your Team under Signing → Product → Archive
```

## First launch on a device
- Tap **Allow** on the "find devices on your local network" prompt (required). If missed: iOS
  **Settings → Casa Vestry → Local Network** → on.
- Enter the mini-PC address. Double-check it — earlier we had `192.167.0.217`, which looks like a typo for
  `192.168.0.217`.

## Troubleshooting
| Problem | Fix |
|---|---|
| "Can't reach …" | Same Wi-Fi as the mini-PC? Panel running on port 3000? Local Network permission on? |
| **View recordings** opens the App Store | Install UniFi Protect and sign in once. Guided Access blocks switching apps on the wall iPad. |
| Snapshot can't save to Photos | iOS **Settings → Casa Vestry → Photos → Add Photos Only** |
| Codemagic: "No matching profiles" | Bundle ID in App Store Connect must match `com.newlogicaltech.casavestry`; re-run Fetch profiles |
| Codemagic: build number already used | Set the real `APP_STORE_APPLE_ID` so it can read the latest TestFlight build |
