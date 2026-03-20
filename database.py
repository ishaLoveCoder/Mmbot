import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

log = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME   = os.getenv("DB_NAME", "moviebot")

_client = AsyncIOMotorClient(MONGO_URI)
_db     = _client[DB_NAME]

# Collections
media_col = _db["movies"]
users_col = _db["users"]
groups_col = _db["groups"]
templates  = _db["templates"]
bans       = _db["bans"]

# Aliases
users  = users_col
groups = groups_col


async def save_media(doc: dict) -> None:
    await media_col.update_one(
        {"msg_id": doc["msg_id"]},
        {"$set": doc},
        upsert=True
    )
    log.info(f"[DB] Saved: {doc.get('title')}")


async def get_media_by_msgid(msg_id: int):
    return await media_col.find_one({"msg_id": msg_id}, {"_id": 0})


async def get_all_media(limit: int = 200, skip: int = 0) -> list:
    cursor = media_col.find({}, {"_id": 0}).sort("added_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)


async def search_media(query: str, limit: int = 20) -> list:
    cursor = media_col.find(
        {"title": {"$regex": query, "$options": "i"}},
        {"_id": 0}
    ).sort("added_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_stats() -> dict:
    total  = await media_col.count_documents({})
    movies = await media_col.count_documents({"type": "movie"})
    series = await media_col.count_documents({"type": "series"})
    try:
        stats   = await _db.command("collstats", "movies")
        db_size = f"{stats['size'] / 1_048_576:.1f} MB"
    except Exception:
        db_size = "N/A"
    return {"total": total, "movies": movies, "series": series, "db_size": db_size}


async def create_indexes() -> None:
    await media_col.create_index("msg_id", unique=True)
    await media_col.create_index("title")
    await media_col.create_index("added_at")
    log.info("[DB] Indexes ready")
