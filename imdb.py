import aiohttp
from bs4 import BeautifulSoup
import json
import logging

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


async def search_movie(query: str) -> list:
    url = f"https://m.imdb.com/find?q={aiohttp.helpers.quote(query)}&s=tt"
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                html = await resp.text()

        soup   = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            return []

        data    = json.loads(script.text)
        results = data["props"]["pageProps"]["titleResults"]["results"]
        movies  = []
        for r in results[:10]:
            item = r.get("listItem", {})
            if item.get("titleId"):
                movies.append({
                    "id":    item["titleId"],
                    "title": item.get("titleText", "Unknown"),
                    "year":  item.get("releaseYear", ""),
                })
        return movies
    except Exception as e:
        log.warning(f"[IMDb Search] Error: {e}")
        return []


async def get_movie(imdb_id: str) -> dict:
    url = f"https://m.imdb.com/title/{imdb_id}/"
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                html = await resp.text()

        soup   = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            return {}

        data  = json.loads(script.text)
        movie = data.get("props", {}).get("pageProps", {}).get("aboveTheFoldData", {})
        if not movie:
            return {}

        # Cast
        actors = []
        try:
            for c in movie["castV2"]["edges"][:10]:
                actors.append(c["node"]["name"]["nameText"]["text"])
        except Exception:
            pass

        # Directors
        directors = []
        try:
            for group in movie.get("principalCredits", []):
                if group.get("category", {}).get("text") == "Director":
                    for d in group.get("credits", []):
                        directors.append(d["name"]["nameText"]["text"])
        except Exception:
            pass

        # Genres
        genres = []
        try:
            for g in movie.get("genres", {}).get("genres", []):
                genres.append(g["text"])
        except Exception:
            pass

        # Rating
        rating, votes = "N/A", 0
        try:
            rating = movie["ratingsSummary"]["aggregateRating"]
            votes  = movie["ratingsSummary"]["voteCount"]
        except Exception:
            pass

        # Plot
        plot = "N/A"
        try:
            plot = movie["plot"]["plotText"]["plainText"]
        except Exception:
            pass

        # Runtime
        runtime = "N/A"
        try:
            runtime = movie["runtime"]["displayableProperty"]["value"]["plainText"]
        except Exception:
            pass

        # Year
        year = "N/A"
        try:
            year = movie["releaseYear"]["year"]
        except Exception:
            pass

        # Poster
        poster = ""
        og = soup.find("meta", property="og:image")
        if og:
            poster = og.get("content", "")

        return {
            "TITLE":      movie.get("titleText", {}).get("text", "Unknown"),
            "YEAR":       year,
            "RATING":     rating,
            "VOTES":      votes,
            "DURATION":   runtime,
            "GENRE":      ", ".join(genres) if genres else "N/A",
            "STORY_LINE": plot,
            "LANGUAGE":   "N/A",
            "IMDB_ID":    imdb_id,
            "IMDB_URL":   f"https://www.imdb.com/title/{imdb_id}/",
            "ACTORS":     ", ".join(actors)    if actors    else "N/A",
            "DIRECTORS":  ", ".join(directors) if directors else "N/A",
            "IMG_POSTER": poster,
        }
    except Exception as e:
        log.warning(f"[IMDb Get] Error: {e}")
        return {}
