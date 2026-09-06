"""Load Apple PKI root certificates for SignedDataVerifier.

Certificates are public Apple Root CAs from
https://www.apple.com/certificateauthority/ — not private keys.

Default directory: backend/certs/apple/
Override with APPLE_ROOT_CA_DIR.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "certs" / "apple"
_CERT_NAMES = (
    "AppleIncRootCertificate.cer",
    "AppleRootCA-G2.cer",
    "AppleRootCA-G3.cer",
)


def apple_root_ca_dir() -> Path:
    override = os.getenv("APPLE_ROOT_CA_DIR", "").strip()
    return Path(override) if override else _DEFAULT_DIR


@lru_cache(maxsize=1)
def load_apple_root_certificates() -> list[bytes]:
    directory = apple_root_ca_dir()
    loaded: list[bytes] = []
    for name in _CERT_NAMES:
        path = directory / name
        if path.is_file():
            data = path.read_bytes()
            if data:
                loaded.append(data)
    if not loaded and directory.is_dir():
        for path in sorted(directory.glob("*.cer")):
            data = path.read_bytes()
            if data:
                loaded.append(data)
    return loaded


def clear_apple_root_certificate_cache() -> None:
    load_apple_root_certificates.cache_clear()
