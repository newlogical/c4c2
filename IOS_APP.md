# Smith Apartment — iOS app (Mac mini)

The iOS app is a thin wrapper. On launch it asks for the controller address once (pre-filled
`192.168.0.217`), checks the mini-PC is reachable, then opens the normal panel from
`http://<address>:3000`. Panel updates still come from the mini-PC (`git pull` + `yarn build`) —
you only rebuild the iOS app to change its icon/name or when a TestFlight build expires (90 days).

Project folder: `ios-app/` in the repo (Capacitor 8).

---

## 1. One-time Mac setup
1. Install **Xcode 26 or newer** from the Mac App Store, open it once, accept the licence and let it
   install components. Then in Terminal: `xcode-select --install`
2. Install **Node.js 22 LTS or newer** from https://nodejs.org (macOS installer).
3. Install **Git** if asked (Terminal: `git --version` offers to install it).
4. Xcode → **Settings → Accounts → +** → sign in with the Apple ID that owns your
   **Apple Developer Program** membership.

## 2. Get the code and build the iOS project
In Terminal:
```bash
cd ~
git clone https://github.com/newlogical/c4c2.git
cd c4c2/ios-app
npm install
npx cap add ios          # creates the ios/ Xcode project (first time only)
npm run patch-ios        # adds the network/full-screen settings to Info.plist
npm run assets           # generates the app icon + launch screen from assets/
npx cap sync ios
npx cap open ios         # opens Xcode
```
Later updates: `git pull`, then `npm run patch-ios && npx cap sync ios`.

## 3. Signing in Xcode
1. In the left sidebar click **App** (blue icon) → **TARGETS: App** → **Signing & Capabilities**.
2. Tick **Automatically manage signing**, choose your **Team**.
3. **Bundle Identifier**: `com.newlogicaltech.smithapartment` (change it if Xcode says it's taken).
4. **General** tab → **Supported Destinations**: keep **iPhone** and **iPad**.

## 4. Try it on a device (cable, quickest test)
1. Plug the iPad (or iPhone) into the Mac, unlock it, tap **Trust**.
2. On the device: **Settings → Privacy & Security → Developer Mode → On** (restart when asked).
3. In Xcode pick the device at the top, press **▶ Run**.
4. On first launch tap **Allow** for "find devices on your local network", confirm the address,
   tap **Connect** — the PIN screen of the panel should appear.

## 5. Install on the iPad and the client's iPhone — TestFlight (no cable)
1. https://appstoreconnect.apple.com → **Apps → + → New App**: platform iOS, name
   **Smith Apartment**, bundle ID from step 3, SKU `smith-apartment`. (It never needs to go public.)
2. Xcode: choose **Any iOS Device (arm64)** at the top → **Product → Archive**.
3. When the Organizer opens: **Distribute App → App Store Connect → Upload** (defaults are fine).
4. After ~10–30 min the build shows in App Store Connect → **TestFlight**.
5. **Users and Access → +**: invite the client with their Apple ID email (role **Marketing** is
   enough). Then **TestFlight → Internal Testing → +** create a group, add yourself and the client,
   add the build. Internal testers need no Apple review.
6. On each device install **TestFlight** from the App Store, open the invite email, **Install**.
7. TestFlight builds expire after **90 days** — repeat steps 2–3 and the devices update.

## 6. Wall-panel iPad tips
- **Settings → Display & Brightness → Auto-Lock → Never**, keep it on the charger.
- Lock it to the app: **Settings → Accessibility → Guided Access → On**, open the app,
  triple-click the side/top button → **Start**.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "Can't reach 192.168.0.217" | Device not on apartment Wi-Fi, mini-PC/panel window not running, wrong address, or "Local Network" was denied: **Settings → Privacy & Security → Local Network → Smith Apartment → On**. |
| Panel opens in Safari instead of inside the app | Tell the developer — the `allowNavigation` list in `capacitor.config.json` needs the exact address. |
| Change the controller address | Force-close the app, reopen, tap **Change controller address** on the connecting screen. |
| Signing errors in Xcode | Re-check the Team in step 3, or change the Bundle Identifier to something unique. |
