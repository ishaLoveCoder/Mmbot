import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

log = logging.getLogger(__name__)

# ─── Lazy connection — auto filter bot jaisa ─────────────────────────────────
class Database:
    def __init__(self, uri: str, db_name: str):
        self.client = AsyncIOMotorClient(uri)
        self.db     = self.client[db_name]
        self.media  = self.db["movies"]
        self.users  = self.db["users"]
        self.groups = self.db["groups"]

    async def save_media(self, doc: dict) -> None:
        await self.media.update_one(
            {"msg_id": doc["msg_id"]},
            {"$set": doc},
            upsert=True
        )
        log.info(f"[DB] Saved: {doc.get('title')}")

    async def get_media_by_msgid(self, msg_id: int):
        return await self.media.find_one({"msg_id": msg_id}, {"_id": 0})

    async def get_all_media(self, limit: int = 200, skip: int = 0) -> list:
        cursor = self.media.find({}, {"_id": 0}).sort("added_at", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def search_media(self, query: str, limit: int = 20) -> list:
        cursor = self.media.find(
            {"title": {"$regex": query, "$options": "i"}},
            {"_id": 0}
        ).sort("added_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_stats(self) -> dict:
        total  = await self.media.count_documents({})
        movies = await self.media.count_documents({"type": "movie"})
        series = await self.media.count_documents({"type": "series"})
        try:
            stats   = await self.db.command("collstats", "movies")
            db_size = f"{stats['size'] / 1_048_576:.1f} MB"
        except Exception:
            db_size = "N/A"
        return {"total": total, "movies": movies, "series": series, "db_size": db_size}

    async def create_indexes(self) -> None:
        await self.media.create_index("msg_id", unique=True)
        await self.media.create_index("title")
        await self.media.create_index("added_at")
        log.info("[DB] Indexes ready")


# ─── Single instance — auto filter bot jaisa ─────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME   = os.getenv("DB_NAME", "moviebot")

db = Database(MONGO_URI, DB_NAME)

# ─── Helper functions (backward compatible) ───────────────────────────────────
async def save_media(doc: dict) -> None:
    await db.save_media(doc)

async def get_media_by_msgid(msg_id: int):
    return await db.get_media_by_msgid(msg_id)

async def get_all_media(limit: int = 200, skip: int = 0) -> list:
    return await db.get_all_media(limit, skip)

async def search_media(query: str, limit: int = 20) -> list:
    return await db.search_media(query, limit)

async def get_stats() -> dict:
    return await db.get_stats()
    
