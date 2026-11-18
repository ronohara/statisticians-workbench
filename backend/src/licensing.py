"""
Golden Screwdriver — Feature Licensing Module.

Reads a signed licence.json file at startup, verifies the Ed25519 signature,
and populates an in-memory set of enabled features. Every gated API endpoint
and UI element checks this set.

If no valid licence file exists (missing, invalid, expired, or tampered), the
system falls back to a build-type default feature set — the full database set
for the open-source edition, or only postgres_db for the commercial edition.
The system must never crash or refuse to start because of a bad licence file.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# ── Hardcoded public key ────────────────────────────────────────────
# Generated once. The corresponding private key is stored outside the
# repo and used by scripts/generate-licence.py to sign new licences.
# Key rotation requires a software update to change this constant.

_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAucjkUZJFJgkzJEcF1ro9W/xiWYV5+tWVBhTY1s5+t2o=
-----END PUBLIC KEY-----"""

# ── Module state ────────────────────────────────────────────────────

ENABLED_FEATURES: set[str] = set()
_licence_info: Optional[dict] = None
_loaded: bool = False


# ── Build type ─────────────────────────────────────────────────────

def is_open_source() -> bool:
    """Return True for the open-source (Python) edition."""
    return True


_OPEN_SOURCE_FEATURES: frozenset[str] = frozenset(
    {"postgres_db", "mysql_db", "mssql_db", "access_db"}
)
_COMMERCIAL_FEATURES: frozenset[str] = frozenset({"postgres_db"})


def _default_features() -> set[str]:
    """The feature set a build enables when no valid licence is present."""
    return set(_OPEN_SOURCE_FEATURES if is_open_source() else _COMMERCIAL_FEATURES)


# ── Public API ──────────────────────────────────────────────────────

def load_licence(path: Optional[str] = None) -> None:
    """
    Load and verify the licence file at startup.

    Reads the JSON licence file, verifies the Ed25519 signature against
    the hardcoded public key, checks expiry, and populates ENABLED_FEATURES.

    If the file is missing, invalid, expired, or tampered, the system
    falls back to the build-type default feature set (open-source or
    commercial). The function logs the reason and never raises.

    Args:
        path: Path to licence.json. If None, uses the LICENCE_FILE env
              var, or defaults to ../licence.json relative to this file.
    """
    global ENABLED_FEATURES, _licence_info, _loaded

    if path is None:
        path = os.getenv(
            "LICENCE_FILE",
            os.path.join(os.path.dirname(__file__), "..", "licence.json"),
        )

    # Reset to the build-type default feature set (open-source or commercial).
    # Every fallback path (missing/invalid/expired/tampered) keeps these
    # defaults; only a valid licence overwrites them.
    ENABLED_FEATURES = _default_features()
    _licence_info = None
    _loaded = True
    mode = "open-source" if is_open_source() else "commercial"

    # Normalise path
    path = os.path.abspath(path)

    if not os.path.exists(path):
        logging.info("No licence file found at %s — running in %s mode", path, mode)
        logging.info("Features enabled: %s", ", ".join(sorted(ENABLED_FEATURES)))
        return

    # ── Read the file ────────────────────────────────────────────
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        logging.error("Failed to read licence file %s: %s", path, e)
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logging.error("Licence file %s is not valid JSON: %s", path, e)
        return

    if not isinstance(data, dict):
        logging.error("Licence file %s has unexpected structure", path)
        return

    # ── Extract and verify signature ─────────────────────────────
    signature_hex = data.pop("signature", None)
    if not signature_hex or not isinstance(signature_hex, str):
        logging.warning("Licence file %s missing signature — rejected", path)
        return

    try:
        signature = bytes.fromhex(signature_hex)
    except (ValueError, TypeError):
        logging.warning("Licence signature in %s is not valid hex — rejected", path)
        return

    # Canonical JSON payload for signature verification:
    # keys sorted, no trailing whitespace, ASCII-encoded
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    try:
        public_key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM.encode())
    except Exception as e:
        logging.error("Failed to load hardcoded public key: %s", e)
        return

    try:
        public_key.verify(signature, payload)
    except InvalidSignature:
        logging.warning(
            "Licence signature verification FAILED for %s — "
            "file may have been tampered with. Running in %s mode.",
            path,
            mode,
        )
        return
    except Exception as e:
        logging.error("Unexpected error during signature verification: %s", e)
        return

    # ── Check expiry ─────────────────────────────────────────────
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry < datetime.now(timezone.utc):
                logging.warning(
                    "Licence expired at %s — running in %s mode", expires_at, mode
                )
                return
        except (ValueError, TypeError):
            logging.warning(
                "Invalid expiry date in licence: %s — rejected", expires_at
            )
            return

    # ── Valid licence — populate state ───────────────────────────
    features = data.get("features", [])
    if not isinstance(features, list):
        logging.warning("Licence 'features' field is not a list — no features enabled")
        features = []

    ENABLED_FEATURES = set(features)
    _licence_info = {
        "tier": "corporate",
        "issued_to": data.get("issued_to", "Unknown"),
        "issued_at": data.get("issued_at"),
        "expires_at": data.get("expires_at"),
        "features": sorted(ENABLED_FEATURES),
        "max_users": data.get("max_users"),
    }

    logging.info(
        "Licence loaded: corporate tier, %d feature(s) [%s], issued to %s",
        len(ENABLED_FEATURES),
        ", ".join(sorted(ENABLED_FEATURES)) if ENABLED_FEATURES else "none",
        _licence_info["issued_to"],
    )


def is_feature_enabled(key: str) -> bool:
    """Return True if the named feature is enabled by the current licence."""
    return key in ENABLED_FEATURES


_DB_TYPE_FEATURE = {
    "postgresql": "postgres_db",
    "mysql": "mysql_db",
    "mssql": "mssql_db",
    "access": "access_db",
}


def feature_for_db_type(db_type: str) -> str | None:
    """Map a database connection type to its licence feature key.

    Returns None for an unknown type (no feature gate applies).
    """
    return _DB_TYPE_FEATURE.get(db_type)


def get_licence_info() -> dict:
    """
    Return a summary of the current licence state.

    Always returns a dict. When no licence is loaded, returns the build-type
    default feature set with tier "open_source" (open-source edition) or
    "commercial" (commercial edition).
    """
    if _licence_info:
        return dict(_licence_info)
    return {
        "tier": "open_source" if is_open_source() else "commercial",
        "features": sorted(ENABLED_FEATURES),
    }


def has_valid_licence() -> bool:
    """Return True when a valid licence is currently loaded."""
    return _licence_info is not None


def get_licence_path() -> str:
    """Return the configured licence file path (does not load it)."""
    return os.path.abspath(
        os.getenv(
            "LICENCE_FILE",
            os.path.join(os.path.dirname(__file__), "..", "licence.json"),
        )
    )


def verify_licence_content(content: str) -> dict:
    """
    Validate a licence JSON string without modifying module state.

    Returns a dict with:
        valid (bool),
        error (str | None) if invalid,
        and the full parsed licence info if valid.

    Does NOT populate ENABLED_FEATURES or _licence_info.
    """
    result: dict = {"valid": False, "error": None}

    # ── Parse JSON ──────────────────────────────────────────────
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        result["error"] = f"Invalid JSON: {e}"
        return result

    if not isinstance(data, dict):
        result["error"] = "Licence must be a JSON object"
        return result

    # ── Extract and verify signature ────────────────────────────
    signature_hex = data.pop("signature", None)
    if not signature_hex or not isinstance(signature_hex, str):
        result["error"] = "Missing signature field"
        return result

    try:
        signature = bytes.fromhex(signature_hex)
    except (ValueError, TypeError):
        result["error"] = "Signature is not valid hex"
        return result

    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    try:
        public_key = serialization.load_pem_public_key(_PUBLIC_KEY_PEM.encode())
    except Exception as e:
        result["error"] = f"Internal error loading public key: {e}"
        return result

    try:
        public_key.verify(signature, payload)
    except InvalidSignature:
        result["error"] = "Signature verification failed — licence may be tampered"
        return result
    except Exception as e:
        result["error"] = f"Signature verification error: {e}"
        return result

    # ── Check expiry ────────────────────────────────────────────
    expires_at = data.get("expires_at")
    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry < datetime.now(timezone.utc):
                result["error"] = f"Licence expired at {expires_at}"
                return result
        except (ValueError, TypeError):
            result["error"] = f"Invalid expiry date: {expires_at}"
            return result

    # ── Valid ───────────────────────────────────────────────────
    features = data.get("features", [])
    if not isinstance(features, list):
        features = []

    result["valid"] = True
    result["tier"] = "corporate"
    result["features"] = features
    result["issued_to"] = data.get("issued_to", "Unknown")
    result["issued_at"] = data.get("issued_at")
    result["expires_at"] = data.get("expires_at")
    result["max_users"] = data.get("max_users")
    return result


def is_loaded() -> bool:
    """Return True if load_licence() has been called (even if no file was found)."""
    return _loaded
