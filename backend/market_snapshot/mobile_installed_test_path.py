"""Test path for the currently released mobile app against an isolated backend.

Does not build, submit, or point production at this worktree.
"""

from __future__ import annotations

PRODUCTION_EAS_API = "https://sportbook-me-production.up.railway.app/api"
BUNDLE_ID = "com.sportbookme.app"
RELEASED_VERSION = "1.1.0"
RELEASED_GIT = "6566d18f35f14db4b5b6941b1da3e405f203f498"
RELEASED_GIT_SUBJECT = "feat: finalize Sportbook Me iOS launch experience"


def installed_app_test_path() -> dict:
    """Report whether the released binary can hit an isolated backend."""
    return {
        "available": False,
        "released_binary_can_target_isolated_backend": False,
        "released_app": {
            "name": "Sportbook ME",
            "version": RELEASED_VERSION,
            "bundle_id": BUNDLE_ID,
            "source_revision": RELEASED_GIT,
            "source_subject": RELEASED_GIT_SUBJECT,
            "eas_production_env": {
                "EXPO_PUBLIC_API_URL": PRODUCTION_EAS_API,
            },
        },
        "prepared_test_build": {
            "source": "ios-launch-release / " + RELEASED_GIT,
            "changes_only": [
                "eas.json development-simulator and development env EXPO_PUBLIC_API_URL",
                "developmentClient true (already on those profiles)",
            ],
            "not_changed": "mobile app source, dependency versions, production profile, bundle id",
            "profile": "development-simulator",
            "paid_build_started": False,
        },
        "build_cost_and_access": {
            "local_simulator": "Free if Xcode is installed: npx expo run:ios --simulator from the released checkout. No EAS minutes.",
            "eas_cloud": "Requires a logged-in Expo account. Free-plan EAS has a monthly build quota; additional builds are billed by Expo. Not started.",
            "device_or_testflight": "Apple Developer Program membership required for device provisioning. Not started. Store submission forbidden.",
            "blocking_before_paid_eas": [
                "Confirm Expo account login (eas whoami).",
                "Confirm remaining free EAS builds or accept paid minutes.",
                "For a physical device, a LAN/tunnel API URL, not 127.0.0.1.",
            ],
        },
        "why": (
            "getApiUrl() returns process.env.EXPO_PUBLIC_API_URL or the hardcoded Railway production URL. "
            "There is no in-app, runtime, or settings override. EAS production bakes EXPO_PUBLIC_API_URL "
            "at build time. A TestFlight or App Store install therefore always calls Railway, never this "
            "worktree’s FastAPI, and never 127.0.0.1."
        ),
        "exact_dependency": {
            "required": [
                "A non-production EAS development or development-simulator client built with EXPO_PUBLIC_API_URL pointed at the isolated FastAPI.",
                "That URL must be a LAN or tunnel address the device can reach. 127.0.0.1 on a phone is the phone itself, not this Mac.",
                "Isolated FastAPI with Redis-backed Market Tools serving (MARKET_TOOLS_ODDSAPI_ENABLED only in that process), collect still off unless a later assignment authorizes it.",
                "A Pro Arena or Elite Stack test account on that isolated backend (paid-through canceled still entitled until current_period_end).",
            ],
            "not_sufficient": [
                "Editing mobile/lib/api.ts in this worktree without a new EAS development build.",
                "The currently released App Store / TestFlight binary.",
                "Source-level live-odds contract projection (game_id / home_team_name / moneyline).",
                "Chrome desktop E2E against the web app.",
            ],
            "blocked_by": "No development EAS client in this assignment is configured for the isolated backend. Mobile submission is forbidden here.",
        },
        "web_e2e_does_not_substitute": True,
        "no_mobile_submission": True,
        "no_runtime_override_added": True,
        "paid_build_started": False,
    }
