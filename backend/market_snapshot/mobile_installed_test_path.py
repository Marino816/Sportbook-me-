"""Test path for the currently distributed iOS app against an isolated backend.

Does not build, submit, or point production at this worktree.
"""

from __future__ import annotations

PRODUCTION_EAS_API = "https://sportbook-me-production.up.railway.app/api"
BUNDLE_ID = "com.sportbookme.app"
APP_STORE_ID = "6808706342"
SIMULATOR_API = "http://127.0.0.1:8010/api"
DEVICE_LAN_API = "http://192.168.1.44:8010/api"

# Public App Store lookup 2026-10-02 (itunes.apple.com/lookup?id=6808706342).
DISTRIBUTED_VERSION = "1.1.1"
DISTRIBUTED_RELEASED_AT = "2026-09-25T14:34:49Z"
DISTRIBUTED_FIRST_RELEASED_AT = "2026-09-22T07:00:00Z"
DISTRIBUTED_BUNDLE_ID = BUNDLE_ID

# Closest committed source matching the live listing (optimizer player draft + owner icon).
# Committed app.json at this revision still has marketing version 1.1.0.
# App Store versionString is 1.1.1. CFBundleVersion is not in committed git
# (production EAS autoIncrement). Dirty repair-batch1 app.json claims buildNumber 11
# and is not treated as a release record.
DISTRIBUTED_SOURCE_GIT = "b91f71b5dbc91b6419ed517b7d51d03fa4d25d96"
DISTRIBUTED_SOURCE_SUBJECT = "feat: replace iOS app icon with owner-approved SB ME artwork"
LAUNCH_SOURCE_GIT = "6566d18f35f14db4b5b6941b1da3e405f203f498"


def installed_app_test_path() -> dict:
    """Report whether the released binary can hit an isolated backend."""
    return {
        "available": False,
        "released_binary_can_target_isolated_backend": False,
        "paid_build_started": False,
        "distributed_app_store": {
            "source": "itunes.apple.com/lookup?id=6808706342",
            "looked_up_at_utc": "2026-10-02T15:48:00Z",
            "track_id": APP_STORE_ID,
            "bundle_id": DISTRIBUTED_BUNDLE_ID,
            "version": DISTRIBUTED_VERSION,
            "current_version_release_date": DISTRIBUTED_RELEASED_AT,
            "first_release_date": DISTRIBUTED_FIRST_RELEASED_AT,
            "cf_bundle_version": None,
            "cf_bundle_version_note": (
                "App Store lookup returns marketing version 1.1.1 only. "
                "Committed git has no ios.buildNumber. production eas.json uses autoIncrement. "
                "Uncommitted repair-batch1 mobile/app.json lists buildNumber 11; that is not an App Store Connect record."
            ),
            "release_notes": "This update refreshes the App Store information to make Sportbook Me DFS AI easier to discover.",
        },
        "source_revision_for_isolated_test": {
            "git": DISTRIBUTED_SOURCE_GIT,
            "subject": DISTRIBUTED_SOURCE_SUBJECT,
            "worktree": "ios-launch-release is 6566d18; mobile-build8/9 are detached at b91f71b",
            "why": (
                "Live App Store screenshots include Optimizer Player Draft (9713a87) and the owner-approved icon (b91f71b). "
                "6566d18 is the earlier 1.1.0 launch commit and is missing those two changes. "
                "A newly adapted Market Tools worktree binary would not prove compatibility with the distributed app."
            ),
            "committed_app_json_version": "1.1.0",
            "app_store_version": DISTRIBUTED_VERSION,
        },
        "prepared_test_build": {
            "source": "b91f71b / " + DISTRIBUTED_SOURCE_GIT,
            "overlay": "backend/market_snapshot/released_eas.isolated.json",
            "changes_only": [
                "eas.json development-simulator EXPO_PUBLIC_API_URL → " + SIMULATOR_API,
                "eas.json development (physical device) EXPO_PUBLIC_API_URL → " + DEVICE_LAN_API,
                "developmentClient true (already on those profiles)",
            ],
            "not_changed": "mobile app source, dependency versions, production profile, bundle id",
            "profiles": {
                "development-simulator": {
                    "url": SIMULATOR_API,
                    "why": "Simulator and this Mac share loopback. 127.0.0.1 is correct here.",
                },
                "development": {
                    "url": DEVICE_LAN_API,
                    "why": "A physical iPhone's 127.0.0.1 is the phone. Use the Mac LAN address (currently 192.168.1.44). Tunnel if not on this Wi-Fi.",
                },
            },
            "paid_build_started": False,
        },
        "build_cost_and_access": {
            "local_simulator": "Free if Xcode is installed: npx expo run:ios --simulator from the b91f71b checkout with the overlay eas.json. No EAS minutes.",
            "eas_cloud": "Requires a logged-in Expo account. Free-plan EAS has a monthly build quota; additional builds are billed by Expo. Not started.",
            "device_or_testflight": "Apple Developer Program membership required for device provisioning. Not started. Store submission forbidden.",
            "blocking_before_paid_eas": [
                "Confirm Expo account login (eas whoami).",
                "Confirm remaining free EAS builds or accept paid minutes.",
                "For a physical device, use the LAN/tunnel URL, not 127.0.0.1.",
            ],
        },
        "why": (
            "getApiUrl() returns process.env.EXPO_PUBLIC_API_URL or the hardcoded Railway production URL. "
            "There is no in-app, runtime, or settings override. EAS production bakes EXPO_PUBLIC_API_URL "
            "at build time. A TestFlight or App Store install therefore always calls Railway."
        ),
        "exact_dependency": {
            "required": [
                "A non-production EAS development or development-simulator client built with EXPO_PUBLIC_API_URL pointed at the isolated FastAPI.",
                "Simulator URL " + SIMULATOR_API + "; physical-device URL " + DEVICE_LAN_API + " (or a tunnel).",
                "Isolated FastAPI with Redis-backed Market Tools serving (MARKET_TOOLS_ODDSAPI_ENABLED only in that process), collect still off unless a later assignment authorizes it.",
                "A Pro Arena or Elite Stack test account on that isolated backend (paid-through canceled still entitled until current_period_end).",
            ],
            "not_sufficient": [
                "Editing mobile/lib/api.ts in this worktree without a new EAS development build.",
                "The currently released App Store / TestFlight binary.",
                "Building newly adapted Market Tools mobile source instead of b91f71b.",
                "Chrome desktop E2E against the web app.",
            ],
            "blocked_by": "No development EAS client in this assignment is configured for the isolated backend. Paid build not started. Mobile submission is forbidden here.",
        },
        "web_e2e_does_not_substitute": True,
        "no_mobile_submission": True,
        "no_runtime_override_added": True,
    }
