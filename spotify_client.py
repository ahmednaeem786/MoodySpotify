# backend/spotify_client.py
import os
import base64
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
# scopes you'll likely need (add as required)
SCOPES = "user-read-private user-read-email user-top-read user-read-recently-played playlist-modify-private playlist-modify-public user-read-playback-state user-modify-playback-state"

def build_auth_url(state: str):
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "show_dialog": "true",
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def _basic_auth_header():
    key = f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    b64 = base64.b64encode(key).decode()
    return {"Authorization": f"Basic {b64}"}


def exchange_code_for_token(code: str):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = _basic_auth_header()
    resp = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    resp.raise_for_status()
    token_json = resp.json()
    # token_json contains: access_token, token_type, expires_in, refresh_token, scope
    return token_json


def refresh_access_token(refresh_token: str):
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    headers = _basic_auth_header()
    resp = requests.post(SPOTIFY_TOKEN_URL, data=data, headers=headers)
    resp.raise_for_status()
    token_json = resp.json()
    return token_json


def api_get(path: str, access_token: str, params=None):
    url = f"{SPOTIFY_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code == 401:
        # caller should handle refresh
        raise Exception("Unauthorized - token may be expired")
    r.raise_for_status()
    return r.json()


def get_user_profile(access_token: str):
    return api_get("/me", access_token)


def get_user_top_tracks(access_token: str, limit=50, time_range="medium_term"):
    params = {"limit": limit, "time_range": time_range}
    return api_get("/me/top/tracks", access_token, params=params)


def get_audio_features(access_token: str, track_ids: list):
    # track_ids: list of spotify track ids (max 100 per request)
    ids = ",".join(track_ids)
    return api_get(f"/audio-features", access_token, params={"ids": ids})
