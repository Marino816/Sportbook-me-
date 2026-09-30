"""Elapsed time and source timestamps from the already-run two-capture provider test.

No further provider calls. Bodies did not change between captures.
"""

CAPTURE_EVIDENCE = {
    "provider_http_this_report": 0,
    "featured_path": "/v4/sports/americanfootball_nfl/odds",
    "props_path": "/v4/sports/americanfootball_nfl/events/d55cb69fed50a09170560b5b75d8de86/odds",
    "capture_1": {
        "featured_retrieved_at": "2026-09-30T15:35:43+00:00",
        "props_retrieved_at": "2026-09-30T15:35:44+00:00",
        "featured_sha256": "2441761b0a898b89ed35d513c944ab2d795ce50b1ef9db651a9706851afc2a97",
        "props_sha256": "9172c1bcbdd3e727a881e1e092f34efd8cf5946c83ebeaa1d89bd4b6ede07331",
    },
    "capture_2": {
        "featured_retrieved_at": "2026-09-30T15:35:44+00:00",
        "props_retrieved_at": "2026-09-30T15:35:44+00:00",
        "featured_sha256": "2441761b0a898b89ed35d513c944ab2d795ce50b1ef9db651a9706851afc2a97",
        "props_sha256": "9172c1bcbdd3e727a881e1e092f34efd8cf5946c83ebeaa1d89bd4b6ede07331",
    },
    "elapsed_featured_seconds": 1,
    "elapsed_props_seconds": 0,
    "body_changed": False,
    "interval_verification": "insufficient",
    "proved_provider_freshness": False,
    "configured_near_window_seconds": {"featured": 300, "props": 600},
    "note": (
        "INSUFFICIENT FOR INTERVAL VERIFICATION. Featured elapsed 1 second and props 0 seconds, "
        "both far below the configured near-window intervals (300s featured / 600s props). "
        "Identical bodies in a 0–1s window do not prove provider last_update freshness. "
        "source_timestamp is bookmaker last_update; retrieved_at is HTTP collection time. "
        "A correctly timed later test must wait at least those intervals between captures."
    ),
}
