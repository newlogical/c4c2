"""Adds the iOS settings the app needs (LAN http, local-network prompt, orientations, Protect detection,
photo saving, TestFlight encryption answer). Safe to re-run; used locally and by Codemagic."""
import plistlib
from pathlib import Path

PLIST = Path(__file__).resolve().parents[1] / "ios/App/App/Info.plist"
ALL = ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationPortraitUpsideDown",
       "UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]

p = plistlib.loads(PLIST.read_bytes())
p.update({
    "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True, "NSAllowsArbitraryLoadsInWebContent": True},
    "NSLocalNetworkUsageDescription": "Casa Vestry connects to your home controller on the local network.",
    "NSPhotoLibraryAddUsageDescription": "Save camera snapshots to your Photos.",
    "LSApplicationQueriesSchemes": ["unifi-protect"],
    "UISupportedInterfaceOrientations": ALL,
    "UISupportedInterfaceOrientations~ipad": ALL,
    "UIRequiresFullScreen": True,
    "UIStatusBarHidden": True,
    "UIViewControllerBasedStatusBarAppearance": False,
    "ITSAppUsesNonExemptEncryption": False,
})
PLIST.write_bytes(plistlib.dumps(p))
print(f"Patched {PLIST}")
