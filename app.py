"""
FastAPI server — same event loop use karta hai bot ke saath.
"""
import os
import logging
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    # Import here to avoid circular import + use correct event loop
    from database import get_all_media
    items = await get_all_media()
    return {"success": True, "count": len(items), "data": items}

@app.get("/api/stats")
async def api_stats():
    from database import get_stats
    s = await get_stats()
    return {"success": True, "data": s}

def run():
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    # Use same event loop as pyrogram
    loop = asyncio.get_event_loop()
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning", loop="none")
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())
