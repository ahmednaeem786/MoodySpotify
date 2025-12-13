# MoodySpotify


**Detect your mood with a webcam and generate Spotify playlists that match it.**  
A demo project combining computer vision (OpenCV), Spotify Web API, and a hybrid recommender to produce personalized, mood-matching playlists. Built for easy demos and portfolio use.

----------------------------------------------------------------------------------

## Why this project
- Demonstrates end-to-end engineering: OAuth, backend API, data pipeline, and frontend UI.  
- Combines CV (emotion detection), music information retrieval (Spotify audio features), and recommender systems.  
- Easy to demo as straightforward log in with Spotify, allow webcam, and see live playlist generation.

----------------------------------------------------------------------------------

## Key features (MVP)
- Spotify OAuth login (fetch top tracks & audio features)
- Local webcam-based mood detection (happy / neutral / sad)
- Hybrid recommender: content-based ranking on Spotify audio features + light personalization
- Streamlit demo UI (or React frontend option)
- Persisted user data (SQLite/Postgres) and simple analytics view

---

## Tech stack
- **Backend:** FastAPI (Python)  
- **Frontend / Demo:** Streamlit (Python) — quick MVP UI  
- **Spotify API:** `spotipy` (Spotify Web API)  
- **CV:** OpenCV + lightweight emotion classifier (local)  
- **ML:** scikit-learn, numpy, pandas  
- **DB:** SQLite (dev) / Postgres (prod)  
- **Dev & Deploy:** Docker, GitHub Actions, VS Code Devcontainer

---