import os
import re
import asyncio
import threading
import logging
from datetime import datetime

from pyrofork import Client, filters
from pyrofork.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app import run as run_web
from imdb import search_movie, get_movie
from database import save_media, get_media_by_msgid, get_all_media, get_stats

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger(__name__)

# ─── ENV ──────────────────────────────────────────────────────────────────────
API_ID         = int(os.getenv("API_ID", "0"))
API_HASH       = os.getenv("API_HASH", "")
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
ADMINS         = [int(x) for x in os.getenv("ADMINS", "0").split()]
SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "")
BOT_USERNAME   = os.getenv("BOT_USERNAME", "")

# ─── BOT CLIENT ───────────────────────────────────────────────────────────────
bot = Client(
    "cinevault",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def extract_title_year(text: str):
    m = re.match(r"^(.+?)\s*\((\d{4})\)", text.strip())
    if m:
        return m.group(1).strip(), m.group(2)
    m = re.search(r"^([\w\s]+?)[\.\s](\d{4})[\.\s]", text.strip())
    if m:
        return m.group(1).replace(".", " ").strip(), m.group(2)
    m = re.match(r"^(.*?)[\.\s](480p|720p|1080p|2160p|4K|HEVC|WEB|BluRay|AMZN)", text, re.I)
    if m:
        return m.group(1).replace(".", " ").strip(), None
    return text[:60].strip(), None

def detect_quality(text: str) -> str:
    for q in ["2160p", "4K", "1080p", "720p", "480p", "360p"]:
        if q.lower() in text.lower():
            return q
    return "Unknown"

def detect_type(text: str) -> str:
    if re.search(r"S\d{2}|Season\s*\d|Series|EP\d{2}|Episode", text, re.I):
        return "series"
    return "movie"

def human_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} GB"
    elif size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} MB"
    return f"{size_bytes / 1024:.1f} KB"

# ─── CHANNEL HANDLER ──────────────────────────────────────────────────────────
@bot.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def on_channel_post(client: Client, message: Message):
    if SOURCE_CHANNEL:
        src = str(SOURCE_CHANNEL)
        if src.startswith("@"):
            if message.chat.username and f"@{message.chat.username}" != src:
                return
        else:
            if str(message.chat.id) != src:
                return

    caption  = message.caption or message.text or ""
    file_obj = message.document or message.video or message.audio
    if not file_obj:
        return

    file_id   = file_obj.file_id
    file_name = getattr(file_obj, "file_name", "") or ""
    file_size = getattr(file_obj, "file_size", 0) or 0
    msg_id    = message.id
    chat_id   = message.chat.id
    file_link = f"https://t.me/{BOT_USERNAME}?start=file_{msg_id}"

    source_text = file_name if file_name else caption
    title, year = extract_title_year(source_text)
    quality     = detect_quality(f"{source_text} {caption}")
    media_type  = detect_type(f"{source_text} {caption}")

    log.info(f"[Channel] {title} ({year}) | {quality}")

    imdb_data = {}
    try:
        query   = f"{title} {year}" if year else title
        results = await search_movie(query)
        if results:
            imdb_data = await get_movie(results[0]["id"])
            log.info(f"[IMDB] {imdb_data.get('TITLE')} ⭐{imdb_data.get('RATING')}")
    except Exception as e:
        log.warning(f"[IMDB] Failed: {e}")

    doc = {
        "title":           imdb_data.get("TITLE") or title,
        "year":            str(imdb_data.get("YEAR") or year or ""),
        "quality":         quality,
        "type":            media_type,
        "file_name":       file_name,
        "file_id":         file_id,
        "msg_id":          msg_id,
        "chat_id":         chat_id,
        "file_link":       file_link,
        "caption":         caption[:600],
        "file_size":       human_size(file_size),
        "file_size_bytes": file_size,
        "added_at":        datetime.utcnow().isoformat(),
        "imdb_id":         imdb_data.get("IMDB_ID", ""),
        "imdb_url":        imdb_data.get("IMDB_URL", ""),
        "imdb_rating":     str(imdb_data.get("RATING", "N/A")),
        "imdb_votes":      imdb_data.get("VOTES", "N/A"),
        "director":        imdb_data.get("DIRECTORS", "N/A"),
        "cast":            imdb_data.get("ACTORS", "N/A"),
        "plot":            imdb_data.get("STORY_LINE", "N/A"),
        "genre":           imdb_data.get("GENRE", "N/A"),
        "runtime":         imdb_data.get("DURATION", "N/A"),
        "language":        imdb_data.get("LANGUAGE", "N/A"),
        "poster_url":      imdb_data.get("IMG_POSTER", ""),
    }

    await save_media(doc)
    log.info(f"[DB] Saved → {doc['title']}")


# ─── /start ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.private & filters.command("start"))
async def start(client: Client, message: Message):
    args = message.command[1:]

    if args and args[0].startswith("file_"):
        try:
            msg_id = int(args[0].replace("file_", ""))
        except ValueError:
            return await message.reply_text("❌ Invalid file ID.")

        record = await get_media_by_msgid(msg_id)
        if not record or not record.get("file_id"):
            return await message.reply_text("❌ File not found.")

        cap = (
            f"🎬 **{record.get('title', '')}** `({record.get('year', '')})`\n"
            f"⭐ IMDb: **{record.get('imdb_rating', 'N/A')}**\n"
            f"🎭 Genre: {record.get('genre', 'N/A')}\n"
            f"⏱ Runtime: {record.get('runtime', 'N/A')}\n"
            f"📽 Director: {record.get('director', 'N/A')}\n"
            f"🌟 Cast: {record.get('cast', 'N/A')}\n"
            f"📦 Quality: {record.get('quality', '')} | 💾 {record.get('file_size', '')}\n\n"
            f"📖 {str(record.get('plot', ''))[:300]}..."
        )
        btn = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 IMDb", url=record.get("imdb_url", "https://imdb.com"))
        ]])

        poster = record.get("poster_url", "")
        if poster and poster.startswith("http"):
            try:
                await message.reply_photo(photo=poster, caption=cap, reply_markup=btn)
            except Exception:
                await message.reply_text(cap, reply_markup=btn)
        else:
            await message.reply_text(cap, reply_markup=btn)

        try:
            await client.send_document(
                chat_id=message.chat.id,
                document=record["file_id"],
                caption=f"🎬 **{record.get('title', '')}** | {record.get('quality', '')} | {record.get('file_size', '')}"
            )
        except Exception as e:
            await message.reply_text(f"⚠️ File send failed: {e}")
        return

    await message.reply_text(
        "🎬 **CineVault Bot**\n\n"
        "Auto-saves movies & series with full IMDb info!\n\n"
        "**Commands:**\n"
        "`/search <title>` — Search IMDb\n"
        "`/latest` — Latest additions\n"
        "`/stats` — Statistics"
    )


# ─── /search ──────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("search"))
async def search_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/search inception`")
    query = " ".join(message.command[1:])
    await message.reply_text(f"🔍 Searching **{query}**...")
    try:
        results = await search_movie(query)
    except Exception as e:
        return await message.reply_text(f"❌ Error: {e}")
    if not results:
        return await message.reply_text("No results found.")
    buttons = [[
        InlineKeyboardButton(
            f"🎬 {r['title']} ({r['year']})",
            callback_data=f"imdb_{r['id']}"
        )
    ] for r in results[:8]]
    await message.reply_text("Select title:", reply_markup=InlineKeyboardMarkup(buttons))


# ─── IMDB CALLBACK ────────────────────────────────────────────────────────────
@bot.on_callback_query(filters.regex(r"^imdb_"))
async def imdb_callback(client, callback):
    imdb_id = callback.data.split("_", 1)[1]
    await callback.answer("Fetching...")
    try:
        data = await get_movie(imdb_id)
    except Exception as e:
        return await callback.message.reply_text(f"❌ Failed: {e}")
    text = (
        f"🎬 **{data.get('TITLE')}** `({data.get('YEAR')})`\n"
        f"⭐ Rating: {data.get('RATING')}/10\n"
        f"🎭 Genre: {data.get('GENRE')}\n"
        f"⏱ Runtime: {data.get('DURATION')}\n"
        f"📽 Director: {data.get('DIRECTORS')}\n"
        f"🌟 Cast: {data.get('ACTORS')}\n\n"
        f"📖 {str(data.get('STORY_LINE', ''))[:400]}..."
    )
    btn = InlineKeyboardMarkup([[
        InlineKeyboardButton("🌐 IMDb", url=data.get("IMDB_URL", "https://imdb.com"))
    ]])
    try:
        await callback.message.reply_photo(
            photo=data.get("IMG_POSTER", ""), caption=text, reply_markup=btn
        )
    except Exception:
        await callback.message.reply_text(text, reply_markup=btn)


# ─── /latest ──────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("latest"))
async def latest_cmd(client: Client, message: Message):
    items = await get_all_media(limit=5)
    if not items:
        return await message.reply_text("No media saved yet.")
    text = "🆕 **Latest Additions:**\n\n"
    buttons = []
    for item in items:
        text += f"• **{item['title']}** ({item.get('year', '')}) ⭐{item.get('imdb_rating', '?')} | {item.get('quality', '')}\n"
        buttons.append([InlineKeyboardButton(
            f"📥 {item['title']} ({item.get('quality', '')})",
            url=item.get("file_link", "https://t.me")
        )])
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ─── /stats ───────────────────────────────────────────────────────────────────
@bot.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_cmd(client: Client, message: Message):
    s = await get_stats()
    await message.reply_text(
        f"📊 **Statistics**\n\n"
        f"🎬 Movies: {s.get('movies', 0)}\n"
        f"📺 Series: {s.get('series', 0)}\n"
        f"📦 Total: {s.get('total', 0)}\n"
        f"🗄 DB Size: {s.get('db_size', 'N/A')}"
    )


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("🌐 Starting web server thread...")
    threading.Thread(target=run_web, daemon=True).start()
    log.info("🤖 Starting CineVault Bot...")
    bot.run()
