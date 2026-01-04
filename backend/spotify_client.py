# backend/spotify_client.py
"""
Spotify helper client used by the FastAPI app.
- Improved error logging for debugging Spotify API errors
- Normalizes track ids (accepts spotify:track:..., open.spotify.com links, or raw ids)
- Chunks requests to /audio-features (Spotify accepts up to 100 ids per request)
- Reads credentials from environment variables when available
"""

import os
import base64
from dotenv import load_dotenv
import requests
from urllib.parse import urlencode
from typing import List, Optional, Dict, Any


# load local .env if present (dev only). Install with: pip install python-dotenv
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")

if not CLIENT_ID or not CLIENT_SECRET:
    # Fail fast in dev so you don't try to run with missing creds
    raise RuntimeError("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET environment variables")

# Debug toggle (set DEBUG_SPOTIFY=0 in env to reduce prints)
DEBUG = os.getenv("DEBUG_SPOTIFY", "1") != "0"

# --- CONFIGURATION ---
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# Scopes required
SCOPES = "user-read-private user-read-email user-top-read user-read-recently-played playlist-modify-private playlist-modify-public"

# -----------------------

def build_auth_url(state: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"

def _basic_auth_header() -> Dict[str, str]:
    key = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    b64 = base64.b64encode(key).decode()
    return {"Authorization": f"Basic {b64}"}

def exchange_code_for_token(code: str) -> Dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = _basic_auth_header()
    resp = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    resp.raise_for_status()
    return resp.json()

def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    headers = _basic_auth_header()
    resp = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    resp.raise_for_status()
    return resp.json()

def api_get(path: str, access_token: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Wrapper around GET to Spotify API. Prints helpful debug info on error,
    including response headers (these sometimes include clues).
    """
    if not path.startswith("/"):
        path = "/" + path
    url = f"{SPOTIFY_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}

    if DEBUG:
        try:
            print(f"DEBUG: api_get -> {url} params={params} token_preview={access_token[:8]}...")
        except Exception:
            pass

    # print("ACCESS_TOKEN =", access_token)

    r = requests.get(url, headers=headers, params=params)

    if not r.ok:
        # Try to parse json error body, fall back to text
        try:
            err_body = r.json()
        except ValueError:
            err_body = r.text

        # Print helpful debug to console including headers
        print("=== SPOTIFY API ERROR ===")
        print("URL:", r.url)
        print("Status:", r.status_code)
        print("Response headers:", dict(r.headers))
        print("Response body:", err_body)
        print("=========================")

        # Raise with context so caller sees the body
        raise requests.HTTPError(f"{r.status_code} Error calling {r.url}: {err_body}", response=r)

    try:
        return r.json()
    except ValueError:
        return r.text

def get_user_profile(access_token: str) -> Dict[str, Any]:
    return api_get("/me", access_token)

def get_user_top_tracks(access_token: str, limit: int = 50, time_range: str = "medium_term") -> Dict[str, Any]:
    params = {"limit": limit, "time_range": time_range}
    return api_get("/me/top/tracks", access_token, params=params)

# ---- Helpers for audio features ----
def _normalize_track_id(t: str) -> Optional[str]:
    """
    Accepts spotify:track:<id>, https://open.spotify.com/track/<id>?si=..., or raw id
    Returns raw id or None if invalid.
    """
    if not t:
        return None
    t = t.strip()
    if t.startswith("spotify:"):
        return t.split(":")[-1]
    if "open.spotify.com" in t:
        # URL might be like /track/<id> or /track/<id>?si=...
        return t.split("/")[-1].split("?")[0]
    return t


def get_audio_features(access_token: str, track_ids: list):
    """
    Spotify has restricted /audio-features for new apps.
    This function now fails gracefully instead of crashing the API.
    """
    try:
        ids = ",".join(track_ids)
        return api_get("/audio-features", access_token, params={"ids": ids})
    except Exception as e:
        print("⚠️ Audio features unavailable:", e)
        return {"audio_features": None}
