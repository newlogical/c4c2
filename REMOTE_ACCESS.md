# Outside access (port forwarding + HTTPS + personal sign-in)

How it works:
- Only **ports 80 and 443** are forwarded to the mini-PC. A small gatekeeper (Caddy) answers them, gets a free
  security certificate automatically, and passes traffic to the controller. Ports 3000 / 8001 stay LAN-only.
- Anyone coming from the internet signs in with **their own username + password + 6-digit authenticator
  code**, then sees the usual **PIN** screen. A device stays signed in for 30 days; the lock button only asks
  for the PIN again.
- 5 wrong tries from one place → that login is blocked from there for 15 minutes.
- Device webhooks, the demo button and the setup guide are never reachable from outside.
- On the apartment Wi-Fi nothing changes: `http://<mini-PC>:3000` with the PIN, as today.

You need: the domain you own, access to its DNS settings, and UniFi admin access. Pick a name such as
**home.yourdomain.com** (used as the example below).

## 1. Check the internet connection can accept connections
UniFi → **Dashboard / Internet** → note the **WAN IP**. Compare it with https://whatismyip.com.
- Same → good.
- Different, or WAN IP starts with `100.64`–`100.127`, `10.` or `192.168.` → the ISP uses shared addressing
  (CGNAT) and port forwarding can't work. Ask the ISP for a public IP (often free/cheap), then continue.

## 2. Give the mini-PC a fixed address
UniFi → **Client Devices** → the mini-PC → **Settings** → **Fixed IP Address** → on (keep its current IP).

## 3. Point your domain at the apartment
At the company that manages the domain's DNS (GoDaddy, Namecheap, Cloudflare, Google/Squarespace…):
- Add an **A record**: name `home`, value = the WAN IP from step 1, TTL 5 min (or Auto).
- On Cloudflare set it to **DNS only** (grey cloud), not proxied.
- **If the apartment's IP can change:** UniFi → **Settings → Internet → (WAN) → Dynamic DNS** keeps the record
  updated automatically if your DNS provider is listed (or use your provider's own dynamic-DNS tool).

## 4. Forward ports 80 and 443 to the mini-PC
UniFi Network → **Settings → Routing → Port Forwarding** (older versions: *Settings → Firewall & Security →
Port Forwarding*; newest: *Settings → Policy Table → Create New Policy → Port Forwarding*):

| Name | WAN port | Forward IP | Forward port | Protocol |
|---|---|---|---|---|
| Smith HTTPS | 443 | mini-PC IP | 443 | TCP |
| Smith cert | 80 | mini-PC IP | 80 | TCP |

Do **not** forward 3000 or 8001.

## 5. Install the gatekeeper on the mini-PC
Auto-start must already be set up (`install-autostart.ps1`). Then in **Admin PowerShell**:
```powershell
cd C:\apartment-controller
git pull
powershell -ExecutionPolicy Bypass -File .\windows\install-autostart.ps1
powershell -ExecutionPolicy Bypass -File .\windows\install-remote-access.ps1 -Domain home.yourdomain.com -Email you@yourdomain.com
```
(The email only receives certificate notices.) It downloads Caddy, opens 80/443 in the Windows firewall,
starts the gatekeeper at every power-on and prints **OK https://home.yourdomain.com is live**.

## 6. Create the logins
On the panel: **Settings → Outside access → Add login**, once for you and once for the client
(password 12+ characters — a short sentence works well). Share the client's username/password privately.

## 7. First sign-in from outside (each person, once)
1. Install an authenticator app (Google Authenticator, Microsoft Authenticator, or iPhone **Passwords**).
2. On mobile data (Wi-Fi off), open **https://home.yourdomain.com** — or in the iOS app tap
   *Settings → Change controller address* and enter `home.yourdomain.com`.
3. Enter username + password → scan the QR code shown → type the 6-digit code → enter the PIN.

## Managing access
- **Settings → Outside access**: change a password, reset someone's code app (lost phone), or remove a login.
  Each of these signs that person out everywhere immediately.
- Changing the panel PIN also signs every outside device out.
- Turn outside access off: `powershell -ExecutionPolicy Bypass -File .\windows\remove-remote-access.ps1`,
  then delete the two port forwards in UniFi.

## Troubleshooting
| Symptom | Check |
|---|---|
| Script says "Not answering yet" | DNS record points at the right IP (`nslookup home.yourdomain.com`), both forwards exist, step 1 isn't CGNAT. Log: `logs\gateway-console.log` |
| Browser shows certificate error | Port 80 must be forwarded too (used to issue the certificate). Re-run step 5 |
| Works outside but not at home on the domain | Use the LAN address at home, or enable NAT loopback/hairpin in UniFi |
| "Too many attempts" | Wait 15 minutes, or use the right password; nothing to reset |
| Code always wrong | Phone clock must be automatic (iOS Settings → General → Date & Time → Set Automatically) |
