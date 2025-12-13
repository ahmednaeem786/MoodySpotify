# backend/app.py
import os
import secrets
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from dotenv import load_dotenv
from datetime import datetime, timedelta

from backend import spotify_client
from backend.models import Base, engine, SessionLocal, User, Track, UserTopTrack

load_dotenv()  # loads .env

app = FastAPI(title="Mood Spotify Companion - Backend")

# create DB tables
Base.metadata.create_all(bind=engine)

# helper session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/auth/login")
def auth_login():
    # generate state (should be stored in session typically)
    state = secrets.token_urlsafe(16)
    url = spotify_client.build_auth_url(state=state)
    return RedirectResponse(url)


@app.get("/auth/callback")
def auth_callback(code: str = None, state: str = None):
    if code is None:
        raise HTTPException(status_code=400, detail="Missing code in callback")
    token_json = spotify_client.exchange_code_for_token(code)
    access_token = token_json["access_token"]
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))

    # get user profile
    profile = spotify_client.get_user_profile(access_token)
    spotify_user_id = profile["id"]
    display_name = profile.get("display_name")

    # store / upsert user
    db = next(get_db())
    user = db.query(User).filter(User.spotify_user_id == spotify_user_id).first()
    if user:
        user.access_token = access_token
        user.refresh_token = refresh_token or user.refresh_token
        user.token_expires = expires_at
    else:
        user = User(
            spotify_user_id=spotify_user_id,
            display_name=display_name,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires=expires_at,
        )
        db.add(user)
    db.commit()
    return JSONResponse({"msg": "auth success", "spotify_user_id": spotify_user_id})


def ensure_valid_access_token(db_user):
    # refresh token if expired or near expiry
    if db_user.token_expires is None or db_user.token_expires <= datetime.utcnow() + timedelta(seconds=60):
        token_json = spotify_client.refresh_access_token(db_user.refresh_token)
        access_token = token_json.get("access_token")
        expires_in = token_json.get("expires_in", 3600)
        db_user.access_token = access_token
        db_user.token_expires = datetime.utcnow() + timedelta(seconds=int(expires_in))
        # sometimes refresh response doesn't return a new refresh_token
        if "refresh_token" in token_json:
            db_user.refresh_token = token_json["refresh_token"]
        db = next(get_db())
        db.add(db_user)
        db.commit()
    return db_user.access_token


@app.get("/api/me")
def api_me(spotify_user_id: str):
    db = next(get_db())
    user = db.query(User).filter(User.spotify_user_id == spotify_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    # ensure token valid
    access_token = ensure_valid_access_token(user)a
    profile = spotify_client.get_user_profile(access_token)
    return profile


@app.get("/api/top-tracks")
def api_top_tracks(spotify_user_id: str, limit: int = 50):
    db = next(get_db())
    user = db.query(User).filter(User.spotify_user_id == spotify_user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    access_token = ensure_valid_access_token(user)
    top_tracks_json = spotify_client.get_user_top_tracks(access_token, limit=limit)
    items = top_tracks_json.get("items", [])

    # store/update tracks and user_top_tracks
    for idx, item in enumerate(items):
        spotify_track_id = item["id"]
        name = item["name"]
        artists = ", ".join([a["name"] for a in item["artists"]])
        album = item["album"]["name"]

        db_track = db.query(Track).filter(Track.spotify_track_id == spotify_track_id).first()
        if not db_track:
            db_track = Track(
                spotify_track_id=spotify_track_id,
                name=name,
                artist=artists,
                album=album,
                audio_features=None,
            )
            db.add(db_track)
            db.commit()
        # add user_top_tracks link
        utt = UserTopTrack(user_id=user.id, track_id=db_track.id, rank=idx + 1)
        db.add(utt)
    db.commit()

    # after storing basic metadata, fetch audio features
    track_ids = [t["id"] for t in items]
    if track_ids:
        # split into chunks of 100 if necessary; here limit is small
        audio_features_json = spotify_client.get_audio_features(access_token, track_ids)
        af_list = audio_features_json.get("audio_features", [])
        # map and update Track.audio_features
        for af in af_list:
            if not af:
                continue
            spotify_id = af["id"]
            db_track = db.query(Track).filter(Track.spotify_track_id == spotify_id).first()
            if db_track:
                db_track.audio_features = af
                db.add(db_track)
        db.commit()

    return {"fetched": len(items)}
