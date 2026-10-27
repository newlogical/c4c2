#!/bin/bash
# Adds the iOS settings the wrapper needs: plain-http to the LAN controller, local-network prompt,
# full-screen iPad, hidden status bar, Protect app detection, and the TestFlight encryption answer. Safe to re-run.
set -e
PLIST="ios/App/App/Info.plist"
[ -f "$PLIST" ] || { echo "Run 'npx cap add ios' first ($PLIST not found)"; exit 1; }
PB=/usr/libexec/PlistBuddy

setkey() { $PB -c "Delete :$1" "$PLIST" 2>/dev/null || true; $PB -c "Add :$1 $2 $3" "$PLIST"; }

$PB -c "Delete :NSAppTransportSecurity" "$PLIST" 2>/dev/null || true
$PB -c "Add :NSAppTransportSecurity dict" "$PLIST"
$PB -c "Add :NSAppTransportSecurity:NSAllowsLocalNetworking bool true" "$PLIST"
$PB -c "Add :NSAppTransportSecurity:NSAllowsArbitraryLoadsInWebContent bool true" "$PLIST"

setkey NSLocalNetworkUsageDescription string "Smith Apartment connects to your home controller on the local network."
setkey UIRequiresFullScreen bool true
setkey UIStatusBarHidden bool true
setkey UIViewControllerBasedStatusBarAppearance bool false
setkey ITSAppUsesNonExemptEncryption bool false
setkey NSPhotoLibraryAddUsageDescription string "Save camera snapshots to your Photos."

# Lets "View recordings" detect the UniFi Protect app (falls back to its App Store page)
$PB -c "Delete :LSApplicationQueriesSchemes" "$PLIST" 2>/dev/null || true
$PB -c "Add :LSApplicationQueriesSchemes array" "$PLIST"
$PB -c "Add :LSApplicationQueriesSchemes:0 string unifi-protect" "$PLIST"

echo "Info.plist patched:"
$PB -c "Print :NSAppTransportSecurity" "$PLIST"
