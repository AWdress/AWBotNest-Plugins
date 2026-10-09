"""Original TMDB title resolution and bounded persistent lookup cache."""
from __future__ import annotations

import json
import re
import time
import unicodedata

from .transport import FetchError


def normalize(title):
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", str(title)).casefold())


def choose_candidate(results, titles, year=None, animation=False):
    targets = {normalize(title) for title in titles if normalize(title)}
    scored = []
    for item in results:
        names = {normalize(item.get(key, "")) for key in ("title", "original_title", "name", "original_name")}
        names.discard("")
        if not names or not targets or not item.get("id"):
            continue
        exact = bool(targets & names)
        partial = any(len(a) >= 4 and len(b) >= 4 and (a in b or b in a) for a in targets for b in names)
        if not exact and not partial:
            continue
        if animation and 16 not in item.get("genre_ids", []):
            continue
        release = item.get("first_air_date") or item.get("release_date") or ""
        candidate_year = release[:4]
        if year and candidate_year.isdigit() and abs(int(candidate_year) - int(year)) > 1:
            continue
        score = (100 if exact else 50) + (10 if year and candidate_year == str(year) else 0)
        scored.append((score, item))
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


def video_item(item, media_type, raw=None):
    raw = raw or {}
    if not item.get("id"):
        return None
    title = (item.get("name") or item.get("title") or raw.get("title") or "").strip()
    poster = item.get("poster_path") or item.get("posterPath") or ""
    if not title or not poster:
        return None
    return {
        "id": str(item["id"]), "tmdbId": int(item["id"]), "type": "tmdb", "mediaType": media_type,
        "title": title[:300], "description": str(item.get("overview") or raw.get("description") or "")[:1000],
        "rating": item.get("vote_average", item.get("rating", 0)) or 0,
        "voteCount": item.get("vote_count", item.get("voteCount", 0)) or 0,
        "popularity": raw.get("popularity") or raw.get("heat") or item.get("popularity") or 0,
        "releaseDate": item.get("first_air_date") or item.get("release_date") or item.get("releaseDate") or "",
        "lastUpdateDate": (item.get("last_episode_to_air") or {}).get("air_date", "") if media_type == "tv"
                          else item.get("release_date", ""), "sourceRank": raw.get("rank", 0),
        "posterPath": poster, "backdropPath": item.get("backdrop_path") or item.get("backdropPath") or "",
        "genreTitle": ",".join(str(g.get("name", "")) for g in item.get("genres", []) if g.get("name")),
        "regionTitle": ",".join(str(c.get("name", "")) for c in item.get("production_countries", []) if c.get("name")),
    }


class Resolver:
    def __init__(self, transport, storage):
        self.transport, self.storage = transport, storage
        self.cache = {}

    async def load(self):
        value = await self.storage.get("tmdb_matches", {})
        if isinstance(value, dict):
            now = time.time()
            self.cache = {key: val for key, val in value.items() if isinstance(val, dict)
                          and val.get("expires", 0) > now}

    async def save(self):
        ordered = sorted(self.cache, key=lambda k: self.cache[k].get("expires", 0), reverse=True)
        bounded, size = {}, 0
        for key in ordered:
            if len(bounded) >= 2500:
                break
            value = self.cache[key]
            if value.get("expires", 0) <= time.time():
                continue
            # Platform storage permits 10 MB per value; include Unicode and JSON escaping.
            cost = len(json.dumps({key: value}, ensure_ascii=False).encode("utf-8"))
            if size + cost <= 8 * 1024 * 1024:
                bounded[key] = value
                size += cost
        self.cache = bounded
        await self.storage.set("tmdb_matches", self.cache)

    async def resolve(self, raw):
        media_type = "movie" if raw.get("mediaType") == "movie" else "tv"
        titles = list(dict.fromkeys([raw.get("title", ""), *(raw.get("searchTitles") or [])]))[:4]
        if media_type == "tv":
            cleaned = [re.sub(r"\s*(?:第[一二三四五六七八九十百\d]+季|season\s*\d+|\d+(?:st|nd|rd|th)\s+season)\s*$", "", title,
                              flags=re.I).strip() for title in titles]
            titles = list(dict.fromkeys([*cleaned, *titles]))[:4]
        year = raw.get("year")
        if year and not str(year).isdigit():
            year = None
        animation = bool(raw.get("animation") or raw.get("requireGenre") == 16)
        tmdb_id = raw.get("tmdbId") or raw.get("id")
        if tmdb_id and str(tmdb_id).isdigit():
            key = "%s:%s" % (media_type, tmdb_id)
        else:
            key = "%s:%s:%s:%s" % (media_type, normalize(titles[0])[:180], year or "", int(animation))
        cached = self.cache.get(key)
        if cached and cached.get("expires", 0) > time.time():
            result = cached.get("item")
            return {**result, "popularity": raw.get("popularity") or raw.get("heat") or result.get("popularity", 0),
                    "sourceRank": raw.get("rank", 0)} if result else None
        if tmdb_id and str(tmdb_id).isdigit():
            details = await self.transport.tmdb_json("/%s/%s" % (media_type, tmdb_id))
            result = video_item(details, media_type, raw)
        elif not any(normalize(t) for t in titles):
            return None
        else:
            result = None
            types = [media_type]
            if animation:
                types = ["tv", "movie"]
            for kind in types:
                for title in titles:
                    if not normalize(title):
                        continue
                    params = {"query": title, "include_adult": "false", "language": raw.get("searchLanguage") or "zh-CN"}
                    if year:
                        params["first_air_date_year" if kind == "tv" else "primary_release_year"] = int(year)
                    payload = await self.transport.tmdb_json("/search/" + kind, params)
                    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                        raise FetchError("TMDB 搜索响应结构无效")
                    candidate = choose_candidate(payload["results"], titles, year, animation)
                    if not candidate and year:
                        params.pop("first_air_date_year" if kind == "tv" else "primary_release_year", None)
                        payload = await self.transport.tmdb_json("/search/" + kind, params)
                        candidate = choose_candidate(payload.get("results", []), titles, None, animation)
                    if candidate:
                        details = await self.transport.tmdb_json("/%s/%s" % (kind, candidate["id"]))
                        result = video_item(details, kind, raw)
                        break
                if result:
                    break
        self.cache[key] = {"item": result, "expires": time.time() + (7 * 86400 if result else 21600)}
        return result
