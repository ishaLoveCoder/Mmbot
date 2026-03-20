"""
FastAPI server — runs alongside the bot in a thread.
Render uses this port to confirm the service is alive.
Also exposes /api/movies for the website.
"""
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from database import get_all_media, get_stats

log = logging.getLogger(__name__)

app = FastAPI(title="CineVault API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "CineVault Running 🎬", "version": "1.0"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/api/movies")
async def api_movies():
    items = await get_all_media()
    return {"success": True, "count": len(items), "data": items}

@app.get("/api/stats")
async def api_stats():
    s = await get_stats()
    return {"success": True, "data": s}

def run():
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
