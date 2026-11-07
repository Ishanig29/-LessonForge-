"""Live research integrations: Tavily (web), Google Books, YouTube Data API.

Each provider returns a list of ``RawSource`` dicts. Providers never invent
data: every field comes straight from the API response, and fields the API
did not return stay ``None``.

Evidence policy (enforced later by the normaliser/verifier):
* Web pages: the text Tavily actually extracted is stored as ``content`` and
  may be used as evidence.
* Books: only metadata is available, so ``content`` is ``None`` → further
  reading only. Google's search snippet is kept in metadata, labelled as such.
* YouTube: no transcript is fetched, so ``content`` is ``None`` →
  supplementary resource only.
"""
from __future__ import annotations

import re
from typing import TypedDict
from urllib.parse import urlparse

from ...utils.errors import MissingCredentials
from ...utils.http import request_json

WEB_CONTENT_LIMIT = 9000  # characters of page text stored per source


class RawSource(TypedDict, total=False):
    source_type: str
    provider: str
    title: str
    url: str | None
    author_or_domain: str | None
    description: str | None
    content: str | None
    published_date: str | None
    metadata: dict
    query: str
    provider_score: float | None


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


class TavilyProvider:
    name = "tavily"
    source_type = "website"
    endpoint = "https://api.tavily.com/search"

    def __init__(self, api_key: str | None, timeout: int = 25):
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[RawSource]:
        if not self.api_key:
            raise MissingCredentials(
                "Web research needs a Tavily API key. Set TAVILY_API_KEY in backend/.env.",
                details={"env_var": "TAVILY_API_KEY"},
            )
        data = request_json(
            "POST",
            self.endpoint,
            service="Tavily",
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "query": query[:400],
                "search_depth": "advanced",
                "chunks_per_source": 3,
                "max_results": max_results,
                "include_raw_content": True,
                "include_answer": False,
            },
        )
        results: list[RawSource] = []
        for item in data.get("results", []) or []:
            url = item.get("url")
            if not url or not item.get("title"):
                continue
            snippet = (item.get("content") or "").strip()
            raw = (item.get("raw_content") or "").strip()
            # Prefer the full extracted text; fall back to Tavily's relevant chunks.
            content = raw[:WEB_CONTENT_LIMIT] if raw else snippet
            results.append(
                RawSource(
                    source_type="website",
                    provider=self.name,
                    title=item["title"].strip()[:500],
                    url=url,
                    author_or_domain=domain_of(url),
                    description=snippet[:1000] or None,
                    content=content or None,
                    published_date=item.get("published_date"),
                    metadata={"tavily_score": item.get("score"), "content_origin": "raw_content" if raw else "chunks"},
                    query=query,
                    provider_score=item.get("score"),
                )
            )
        return results


class GoogleBooksProvider:
    name = "google_books"
    source_type = "book"
    endpoint = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: str | None, timeout: int = 25):
        self.api_key = api_key  # optional for this API
        self.timeout = timeout

    def search(self, query: str, max_results: int = 4) -> list[RawSource]:
        params = {"q": query[:300], "maxResults": max_results, "printType": "books", "langRestrict": "en"}
        if self.api_key:
            params["key"] = self.api_key
        data = request_json("GET", self.endpoint, service="Google Books", timeout=self.timeout, params=params)
        results: list[RawSource] = []
        for item in data.get("items", []) or []:
            info = item.get("volumeInfo", {}) or {}
            title = info.get("title")
            if not title:
                continue
            if info.get("subtitle"):
                title = f"{title}: {info['subtitle']}"
            isbns = {i.get("type"): i.get("identifier") for i in info.get("industryIdentifiers", []) or []}
            access = item.get("accessInfo", {}) or {}
            results.append(
                RawSource(
                    source_type="book",
                    provider=self.name,
                    title=title[:500],
                    url=info.get("canonicalVolumeLink") or info.get("infoLink"),
                    author_or_domain=", ".join(info.get("authors", []) or []) or None,
                    description=(info.get("description") or "")[:2000] or None,
                    content=None,  # metadata only — the book itself was not read
                    published_date=info.get("publishedDate"),
                    metadata={
                        "publisher": info.get("publisher"),
                        "isbn_13": isbns.get("ISBN_13"),
                        "isbn_10": isbns.get("ISBN_10"),
                        "page_count": info.get("pageCount"),
                        "categories": info.get("categories"),
                        "preview_link": info.get("previewLink"),
                        "viewability": access.get("viewability"),
                        "google_search_snippet": (item.get("searchInfo") or {}).get("textSnippet"),
                        "volume_id": item.get("id"),
                        "access_note": "Metadata only. Full text was not accessed.",
                    },
                    query=query,
                    provider_score=None,
                )
            )
        return results


_ISO_DURATION = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_iso_duration(value: str | None) -> int | None:
    """Convert an ISO-8601 duration like PT12M30S to seconds."""
    if not value:
        return None
    m = _ISO_DURATION.fullmatch(value)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


class YouTubeProvider:
    name = "youtube"
    source_type = "youtube"
    search_endpoint = "https://www.googleapis.com/youtube/v3/search"
    videos_endpoint = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: str | None, timeout: int = 25):
        self.api_key = api_key
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[RawSource]:
        if not self.api_key:
            raise MissingCredentials(
                "YouTube search needs a YouTube Data API key. Set YOUTUBE_API_KEY in backend/.env.",
                details={"env_var": "YOUTUBE_API_KEY"},
            )
        data = request_json(
            "GET",
            self.search_endpoint,
            service="YouTube",
            timeout=self.timeout,
            params={
                "part": "snippet",
                "type": "video",
                "q": query[:300],
                "maxResults": max_results,
                "relevanceLanguage": "en",
                "safeSearch": "strict",
                "videoEmbeddable": "true",
                "key": self.api_key,
            },
        )
        items = [i for i in data.get("items", []) or [] if (i.get("id") or {}).get("videoId")]
        if not items:
            return []
        ids = [i["id"]["videoId"] for i in items]
        details: dict[str, dict] = {}
        try:
            vdata = request_json(
                "GET",
                self.videos_endpoint,
                service="YouTube",
                timeout=self.timeout,
                params={"part": "contentDetails,statistics", "id": ",".join(ids), "key": self.api_key},
            )
            details = {v["id"]: v for v in vdata.get("items", []) or []}
        except Exception:  # duration is optional; keep search results
            details = {}
        results: list[RawSource] = []
        for item in items:
            vid = item["id"]["videoId"]
            sn = item.get("snippet", {}) or {}
            det = details.get(vid, {})
            thumbs = sn.get("thumbnails", {}) or {}
            thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
            duration_s = parse_iso_duration((det.get("contentDetails") or {}).get("duration"))
            results.append(
                RawSource(
                    source_type="youtube",
                    provider=self.name,
                    title=(sn.get("title") or "Untitled video")[:500],
                    url=f"https://www.youtube.com/watch?v={vid}",
                    author_or_domain=sn.get("channelTitle"),
                    description=(sn.get("description") or "")[:1500] or None,
                    content=None,  # transcript not retrieved
                    published_date=sn.get("publishedAt"),
                    metadata={
                        "video_id": vid,
                        "channel_id": sn.get("channelId"),
                        "thumbnail": thumb,
                        "duration_seconds": duration_s,
                        "view_count": (det.get("statistics") or {}).get("viewCount"),
                        "access_note": "Metadata and description only. No transcript was read.",
                    },
                    query=query,
                    provider_score=None,
                )
            )
        return results
