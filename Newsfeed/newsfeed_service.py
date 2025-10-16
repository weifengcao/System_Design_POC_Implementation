"""
Minimal Newsfeed service POC that follows the design documented in design.md.

The implementation keeps the architecture boundaries from the design but backs
them with simple in-memory data structures so the service can be exercised
without external dependencies. The main focus is on illustrating how the feed,
breaking news, and TTS services collaborate.

Endpoints (simple HTTP, not production ready):
    - POST  /users                         -> create a user
    - POST  /interests                     -> upsert a user interest
    - POST  /items                         -> ingest a content item
    - POST  /items/{id}/topics             -> attach topic scores to an item
    - GET   /feed?user_id=1&lang=en        -> fetch ranked feed
    - GET   /item/{id}/tts?lang=en         -> request or fetch cached TTS asset
    - POST  /breaking                      -> mark an item as breaking news
    - GET   /breaking                      -> retrieve recent breaking items

Running the module starts a simple HTTP server on localhost:8077 with a few
sample users, interests, and items pre-loaded so the feed is immediately usable.
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import defaultdict, deque
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# ---------------------------------------------------------------------------
# Data models


@dataclass
class User:
    user_id: int
    locale: str
    region: str
    language_preferences: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Interest:
    user_id: int
    interest_type: str  # 'topic' | 'publisher' | 'entity'
    object_id: str
    weight: float
    language: str


@dataclass
class Item:
    item_id: int
    url: str
    title: str
    summary: str
    language: str
    media_type: str
    publish_ts: datetime
    publisher: str
    main_image_url: Optional[str] = None
    video_manifest_url: Optional[str] = None
    audio_url: Optional[str] = None
    cluster_id: Optional[str] = None
    policy_flags: int = 0
    source_quality: float = 0.5
    popularity: float = 0.1


@dataclass
class ItemTopic:
    item_id: int
    topic_id: str
    score: float


@dataclass
class TTSAsset:
    item_id: int
    language: str
    voice: str
    audio_url: str
    status: str
    duration_seconds: int
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Storage facsimiles


class MetadataStore:
    """Rough stand-in for Postgres/Cassandra metadata storage."""

    def __init__(self) -> None:
        self._users: Dict[int, User] = {}
        self._interests: Dict[int, Dict[Tuple[str, str], Interest]] = defaultdict(dict)
        self._items: Dict[int, Item] = {}
        self._item_topics: Dict[int, Dict[str, ItemTopic]] = defaultdict(dict)
        self._user_seq = 1
        self._item_seq = 1
        self._lock = threading.Lock()

    # --- user operations -------------------------------------------------

    def create_user(self, locale: str, region: str, languages: Optional[List[str]] = None) -> User:
        with self._lock:
            user_id = self._user_seq
            self._user_seq += 1
        user = User(user_id=user_id, locale=locale, region=region, language_preferences=languages or [])
        self._users[user_id] = user
        return user

    def get_user(self, user_id: int) -> "Optional[User]":
        return self._users.get(user_id)

    # --- interest operations ---------------------------------------------

    def upsert_interest(self, interest: Interest) -> None:
        key = (interest.interest_type, interest.object_id)
        self._interests[interest.user_id][key] = interest

    def get_interests(self, user_id: int, *, language: Optional[str] = None) -> List[Interest]:
        interests = list(self._interests[user_id].values())
        if language is None:
            return interests
        return [i for i in interests if i.language == language or i.language == "any"]

    def remove_interest(self, user_id: int, interest_type: str, object_id: str) -> bool:
        key = (interest_type, object_id)
        if key in self._interests[user_id]:
            del self._interests[user_id][key]
            return True
        return False

    def list_topics(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for topic_map in self._item_topics.values():
            for topic_id in topic_map:
                counts[topic_id] += 1
        # Sort by frequency descending
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

    # --- item operations -------------------------------------------------

    def create_item(self, **fields) -> Item:
        with self._lock:
            item_id = self._item_seq
            self._item_seq += 1
        item = Item(item_id=item_id, **fields)
        self._items[item_id] = item
        return item

    def get_item(self, item_id: int) -> "Optional[Item]":
        return self._items.get(item_id)

    def list_items(self) -> Iterable[Item]:
        return self._items.values()

    def upsert_item_topic(self, item_topic: ItemTopic) -> None:
        self._item_topics[item_topic.item_id][item_topic.topic_id] = item_topic

    def get_item_topics(self, item_id: int) -> List[ItemTopic]:
        return list(self._item_topics[item_id].values())


class FeatureCache:
    """Lightweight Redis-style cache with TTL support."""

    def __init__(self) -> None:
        self._values: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def set(self, key: str, value: float, ttl_seconds: int) -> None:
        expires = time.time() + ttl_seconds
        with self._lock:
            self._values[key] = (value, expires)

    def get(self, key: str) -> "Optional[float]":
        now = time.time()
        with self._lock:
            entry = self._values.get(key)
            if not entry:
                return None
            value, expires = entry
            if expires < now:
                del self._values[key]
                return None
            return value


class FeedCache:
    """User feed cache with TTL and basic invalidation."""

    def __init__(self, ttl_seconds: int = 60) -> None:
        self._ttl = ttl_seconds
        self._cache: Dict[int, Tuple[float, List[Dict[str, object]]]] = {}
        self._lock = threading.Lock()

    def get(self, user_id: int) -> Optional[List[Dict[str, object]]]:
        now = time.time()
        with self._lock:
            entry = self._cache.get(user_id)
            if not entry:
                return None
            expires_at, items = entry
            if expires_at < now:
                del self._cache[user_id]
                return None
            return items

    def set(self, user_id: int, feed_items: List[Dict[str, object]]) -> None:
        with self._lock:
            self._cache[user_id] = (time.time() + self._ttl, feed_items)

    def invalidate(self, user_id: Optional[int] = None) -> None:
        with self._lock:
            if user_id is None:
                self._cache.clear()
            else:
                self._cache.pop(user_id, None)


# ---------------------------------------------------------------------------
# Services


class CandidateGenerator:
    """Generates feed candidates using topic overlap and recency filters."""

    def __init__(self, store: MetadataStore) -> None:
        self._store = store

    def generate(self, user: User, interests: List[Interest], language: str, limit: int = 200) -> List[Item]:
        now = datetime.now(timezone.utc)
        interests_by_topic = {
            interest.object_id: interest.weight for interest in interests if interest.interest_type == "topic"
        }
        preferred_languages = set(user.language_preferences or []) | {language}
        candidates: List[Tuple[float, Item]] = []
        for item in self._store.list_items():
            if item.language not in preferred_languages:
                continue
            # Skip content older than 72 hours unless explicitly popular.
            age_hours = (now - item.publish_ts).total_seconds() / 3600
            if age_hours > 72 and item.popularity < 0.3:
                continue
            overlap = 0.0
            for topic in self._store.get_item_topics(item.item_id):
                weight = interests_by_topic.get(topic.topic_id)
                if weight:
                    overlap += weight * topic.score
            # Always include highly popular items even with low overlap.
            base = overlap + item.popularity
            if base > 0.05:
                candidates.append((base, item))
        # Sort by raw overlap/popularity before detailed ranking.
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in candidates[:limit]]


class FeedRanker:
    """Implements the design's heuristic ranking function."""

    def __init__(self, feature_cache: FeatureCache) -> None:
        self._feature_cache = feature_cache
        self._weights = {
            "freshness": 0.4,
            "overlap": 0.3,
            "source_quality": 0.2,
            "popularity": 0.1,
        }

    def rank(
        self,
        user: User,
        interests: List[Interest],
        candidates: List[Item],
        store: MetadataStore,
        *,
        now: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[Tuple[Item, float]]:
        now = now or datetime.now(timezone.utc)
        topic_weights = {
            interest.object_id: interest.weight for interest in interests if interest.interest_type == "topic"
        }
        ranked: List[Tuple[Item, float]] = []
        seen_clusters: set[str] = set()
        for item in candidates:
            if item.cluster_id and item.cluster_id in seen_clusters:
                continue
            age_hours = max((now - item.publish_ts).total_seconds() / 3600, 0.1)
            freshness = math.exp(-age_hours / 12.0)
            overlap = 0.0
            for topic in store.get_item_topics(item.item_id):
                overlap += topic_weights.get(topic.topic_id, 0.0) * topic.score
            source_quality = item.source_quality
            popularity = max(item.popularity, self._feature_cache.get(f"cluster_heat:{item.cluster_id}") or 0.0)
            score = (
                self._weights["freshness"] * freshness
                + self._weights["overlap"] * overlap
                + self._weights["source_quality"] * source_quality
                + self._weights["popularity"] * popularity
            )
            ranked.append((item, score))
            if item.cluster_id:
                seen_clusters.add(item.cluster_id)
        ranked.sort(key=lambda pair: pair[1], reverse=True)
        # Add a couple of exploration items if available.
        exploration: List[Tuple[Item, float]] = []
        for item in candidates:
            if item.cluster_id and item.cluster_id in seen_clusters:
                continue
            if item.publisher != "explore" and item.popularity < 0.2:
                continue
            exploration.append((item, item.popularity))
            if len(exploration) == 2:
                break
        merged = ranked[: limit - len(exploration)] + exploration
        merged.sort(key=lambda pair: pair[1], reverse=True)
        return merged[:limit]


class FeedService:
    """Coordinates candidate generation, ranking, and caching."""

    def __init__(self, store: MetadataStore, cache: FeedCache, candidate_gen: CandidateGenerator, ranker: FeedRanker):
        self._store = store
        self._cache = cache
        self._candidate_gen = candidate_gen
        self._ranker = ranker

    def get_feed(self, user_id: int, language: str, limit: int = 20) -> List[Dict[str, object]]:
        cached = self._cache.get(user_id)
        if cached:
            return cached
        user = self._store.get_user(user_id)
        if user is None:
            raise ValueError(f"user {user_id} not found")
        interests = self._store.get_interests(user_id, language=language)
        candidates = self._candidate_gen.generate(user, interests, language)
        ranked = self._ranker.rank(user, interests, candidates, self._store, limit=limit)
        now = datetime.now(timezone.utc)
        serialized: List[Dict[str, object]] = []
        for item, score in ranked:
            serialized.append(
                {
                    "id": item.item_id,
                    "url": item.url,
                    "title": item.title,
                    "summary": item.summary,
                    "publisher": item.publisher,
                    "language": item.language,
                    "media_type": item.media_type,
                    "publish_ts": item.publish_ts.isoformat(),
                    "main_image_url": item.main_image_url,
                    "video_manifest_url": item.video_manifest_url,
                    "audio_url": item.audio_url,
                    "score": round(score, 4),
                    "cluster_id": item.cluster_id,
                    "popularity": round(item.popularity, 4),
                    "age_hours": round((now - item.publish_ts).total_seconds() / 3600, 2),
                }
            )
        self._cache.set(user_id, serialized)
        return serialized

    def invalidate_user(self, user_id: int) -> None:
        self._cache.invalidate(user_id)

    def invalidate_all(self) -> None:
        self._cache.invalidate()


class TTSService:
    """Simulates on-demand TTS generation and caching."""

    def __init__(self) -> None:
        self._assets: Dict[Tuple[int, str, str], TTSAsset] = {}
        self._lock = threading.Lock()

    def get_or_create_asset(self, item: Item, language: str, voice: Optional[str] = None) -> TTSAsset:
        voice = voice or self._default_voice(language)
        key = (item.item_id, language, voice)
        with self._lock:
            asset = self._assets.get(key)
            if asset and asset.status == "ready":
                return asset
            audio_url = f"https://cdn.newsfeed/audio/{item.item_id}_{language}_{voice}.mp3"
            # In a real system synthesis would be asynchronous. Here we mark as ready immediately.
            asset = TTSAsset(
                item_id=item.item_id,
                language=language,
                voice=voice,
                audio_url=audio_url,
                status="ready",
                duration_seconds=max(int(len(item.summary.split()) / 2.5), 45),
            )
            self._assets[key] = asset
            return asset

    @staticmethod
    def _default_voice(language: str) -> str:
        return "en-US-studio" if language.lower().startswith("en") else "zh-CN-standard"


class BreakingNewsService:
    """Keeps track of breaking news events and supports simple fan-out."""

    def __init__(self, max_items: int = 50) -> None:
        self._recent: Deque[Dict[str, object]] = deque(maxlen=max_items)
        self._subscribers: List[Callable[[Dict[str, object]], None]] = []
        self._lock = threading.Lock()

    def publish(self, event: Dict[str, object]) -> None:
        event = dict(event)
        event["published_at"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._recent.appendleft(event)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                continue

    def recent(self, limit: int = 20) -> List[Dict[str, object]]:
        with self._lock:
            return list(list(self._recent)[:limit])

    def subscribe(self, callback: Callable[[Dict[str, object]], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)


# ---------------------------------------------------------------------------
# Application facade


class NewsfeedApplication:
    """Facade that wires the services together and exposes convenient helpers."""

    def __init__(self) -> None:
        self.store = MetadataStore()
        self.feature_cache = FeatureCache()
        self.feed_cache = FeedCache(ttl_seconds=90)
        self.candidate_gen = CandidateGenerator(self.store)
        self.ranker = FeedRanker(self.feature_cache)
        self.feed_service = FeedService(self.store, self.feed_cache, self.candidate_gen, self.ranker)
        self.tts_service = TTSService()
        self.breaking_service = BreakingNewsService()

    # --- helper methods for HTTP layer ----------------------------------

    def create_user(self, locale: str, region: str, languages: Optional[List[str]] = None) -> User:
        return self.store.create_user(locale=locale, region=region, languages=languages)

    def upsert_interest(self, payload: Dict[str, object]) -> None:
        interest = Interest(
            user_id=int(payload["user_id"]),
            interest_type=str(payload["type"]),
            object_id=str(payload["object_id"]),
            weight=float(payload.get("weight", 1.0)),
            language=str(payload.get("language", "any")),
        )
        self.store.upsert_interest(interest)
        self.feed_service.invalidate_user(interest.user_id)

    def remove_interest(self, payload: Dict[str, object]) -> bool:
        user_id = int(payload["user_id"])
        removed = self.store.remove_interest(user_id, str(payload["type"]), str(payload["object_id"]))
        if removed:
            self.feed_service.invalidate_user(user_id)
        return removed

    def ingest_item(self, payload: Dict[str, object]) -> Item:
        publish_ts = datetime.fromisoformat(payload["publish_ts"])
        item = self.store.create_item(
            url=str(payload["url"]),
            title=str(payload["title"]),
            summary=str(payload.get("summary", "")),
            language=str(payload["language"]),
            media_type=str(payload.get("media_type", "text")),
            publish_ts=publish_ts if publish_ts.tzinfo else publish_ts.replace(tzinfo=timezone.utc),
            publisher=str(payload.get("publisher", "unknown")),
            main_image_url=payload.get("main_image_url"),
            video_manifest_url=payload.get("video_manifest_url"),
            audio_url=payload.get("audio_url"),
            cluster_id=payload.get("cluster_id"),
            policy_flags=int(payload.get("policy_flags", 0)),
            source_quality=float(payload.get("source_quality", 0.5)),
            popularity=float(payload.get("popularity", 0.1)),
        )
        topics = payload.get("topics", [])
        for topic_payload in topics:
            topic = ItemTopic(
                item_id=item.item_id,
                topic_id=str(topic_payload["topic_id"]),
                score=float(topic_payload.get("score", 0.5)),
            )
            self.store.upsert_item_topic(topic)
        self.feed_service.invalidate_all()
        if item.popularity > 0.7:
            self.feature_cache.set(f"cluster_heat:{item.cluster_id}", item.popularity, ttl_seconds=3600)
        return item

    def add_item_topic(self, item_id: int, payload: Dict[str, object]) -> None:
        topic = ItemTopic(
            item_id=item_id,
            topic_id=str(payload["topic_id"]),
            score=float(payload.get("score", 0.5)),
        )
        self.store.upsert_item_topic(topic)
        self.feed_service.invalidate_all()

    def get_feed(self, user_id: int, language: str, limit: int = 20) -> List[Dict[str, object]]:
        return self.feed_service.get_feed(user_id, language, limit=limit)

    def get_tts(self, item_id: int, language: str, voice: Optional[str] = None) -> Dict[str, object]:
        item = self.store.get_item(item_id)
        if item is None:
            raise ValueError(f"item {item_id} not found")
        asset = self.tts_service.get_or_create_asset(item, language, voice)
        return {
            "item_id": asset.item_id,
            "language": asset.language,
            "voice": asset.voice,
            "status": asset.status,
            "audio_url": asset.audio_url,
            "duration_seconds": asset.duration_seconds,
        }

    def publish_breaking(self, payload: Dict[str, object]) -> None:
        if "item_id" in payload:
            item = self.store.get_item(int(payload["item_id"]))
            if not item:
                raise ValueError("unknown item_id for breaking event")
            event = {
                "type": "item",
                "item_id": item.item_id,
                "title": item.title,
                "url": item.url,
                "language": item.language,
                "publisher": item.publisher,
            }
        else:
            event = {
                "type": "manual",
                "title": payload["title"],
                "url": payload.get("url"),
                "language": payload.get("language", "en"),
            }
        self.breaking_service.publish(event)

    def get_breaking(self, limit: int = 20) -> List[Dict[str, object]]:
        return self.breaking_service.recent(limit=limit)

    def list_topics(self) -> List[Dict[str, object]]:
        topics = self.store.list_topics()
        return [{"id": topic_id, "count": count} for topic_id, count in topics.items()]

    def list_users(self) -> List[Dict[str, object]]:
        return [
            {
                "id": user.user_id,
                "locale": user.locale,
                "region": user.region,
                "created_at": user.created_at.isoformat(),
                "languages": user.language_preferences,
            }
            for user in self.store._users.values()
        ]

    def list_user_interests(self, user_id: int) -> List[Dict[str, object]]:
        interests = self.store.get_interests(user_id)
        return [
            {
                "type": interest.interest_type,
                "object_id": interest.object_id,
                "weight": interest.weight,
                "language": interest.language,
            }
            for interest in interests
        ]


# ---------------------------------------------------------------------------
# HTTP layer


STATIC_DIR = Path(__file__).parent / "static"


class RequestHandler(BaseHTTPRequestHandler):
    """Very small JSON-over-HTTP handler that delegates to the application."""

    app = NewsfeedApplication()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._handle_static("index.html")
        elif parsed.path.startswith("/static/"):
            filename = parsed.path[len("/static/") :]
            self._handle_static(filename)
        elif parsed.path == "/feed":
            self._handle_feed(parsed.query)
        elif parsed.path == "/users":
            self._handle_users()
        elif parsed.path.startswith("/users/") and parsed.path.endswith("/interests"):
            self._handle_user_interests(parsed.path)
        elif parsed.path == "/topics":
            self._handle_topics()
        elif parsed.path.startswith("/item/") and parsed.path.endswith("/tts"):
            self._handle_tts(parsed.path, parsed.query)
        elif parsed.path == "/breaking":
            self._handle_breaking(parsed.query)
        else:
            self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        payload = json.loads(body.decode("utf-8") or "{}")
        try:
            if parsed.path == "/users":
                locale = payload.get("locale", "en_US")
                region = payload.get("region", "US")
                languages = payload.get("languages")
                user = self.app.create_user(locale=locale, region=region, languages=languages)
                self._write_json({"user_id": user.user_id}, status=HTTPStatus.CREATED)
            elif parsed.path == "/interests":
                self.app.upsert_interest(payload)
                self._write_json({"status": "ok"})
            elif parsed.path == "/items":
                item = self.app.ingest_item(payload)
                self._write_json({"item_id": item.item_id}, status=HTTPStatus.CREATED)
            elif parsed.path.startswith("/items/") and parsed.path.endswith("/topics"):
                item_id = int(parsed.path.split("/")[2])
                self.app.add_item_topic(item_id, payload)
                self._write_json({"status": "ok"})
            elif parsed.path == "/breaking":
                self.app.publish_breaking(payload)
                self._write_json({"status": "ok"})
            else:
                self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except KeyError as exc:
            self._write_json({"error": f"missing field: {exc}"}, status=HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        payload = json.loads(body.decode("utf-8") or "{}")
        if parsed.path == "/interests":
            try:
                removed = self.app.remove_interest(payload)
                if removed:
                    self._write_json({"status": "ok"})
                else:
                    self._write_json({"status": "not_found"}, status=HTTPStatus.NOT_FOUND)
            except (ValueError, KeyError) as exc:
                self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        else:
            self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    # --- handlers --------------------------------------------------------

    def _handle_feed(self, query: str) -> None:
        params = parse_qs(query)
        try:
            user_id = int(params.get("user_id", [None])[0])
            language = params.get("lang", ["en"])[0]
            limit = int(params.get("limit", ["20"])[0])
        except (TypeError, ValueError):
            self._write_json({"error": "invalid query parameters"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not user_id:
            self._write_json({"error": "user_id required"}, status=HTTPStatus.BAD_REQUEST)
            return
        try:
            feed = self.app.get_feed(user_id, language, limit=limit)
            self._write_json({"items": feed})
        except ValueError as exc:
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_tts(self, path: str, query: str) -> None:
        parts = path.strip("/").split("/")
        try:
            item_id = int(parts[1])
        except (IndexError, ValueError):
            self._write_json({"error": "invalid item id"}, status=HTTPStatus.BAD_REQUEST)
            return
        params = parse_qs(query)
        language = params.get("lang", ["en"])[0]
        voice = params.get("voice", [None])[0]
        try:
            asset = self.app.get_tts(item_id, language, voice=voice)
            self._write_json(asset)
        except ValueError as exc:
            self._write_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def _handle_breaking(self, query: str) -> None:
        params = parse_qs(query)
        limit = int(params.get("limit", ["20"])[0])
        items = self.app.get_breaking(limit=limit)
        self._write_json({"items": items})

    def _handle_users(self) -> None:
        self._write_json({"users": self.app.list_users()})

    def _handle_topics(self) -> None:
        self._write_json({"topics": self.app.list_topics()})

    def _handle_user_interests(self, path: str) -> None:
        parts = path.strip("/").split("/")
        try:
            user_id = int(parts[1])
        except (IndexError, ValueError):
            self._write_json({"error": "invalid user id"}, status=HTTPStatus.BAD_REQUEST)
            return
        interests = self.app.list_user_interests(user_id)
        self._write_json({"interests": interests})

    def _handle_static(self, filename: str) -> None:
        root = STATIC_DIR.resolve()
        target = (root / filename).resolve()
        try:
            if not target.is_file() or not str(target).startswith(str(root)):
                raise FileNotFoundError
            data = target.read_bytes()
            if filename.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif filename.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif filename.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            else:
                content_type = "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self._write_json({"error": "static asset not found"}, status=HTTPStatus.NOT_FOUND)

    # --- utils -----------------------------------------------------------

    def _write_json(self, payload: Dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:  # noqa: A003  (keep quiet output)
        return


# ---------------------------------------------------------------------------
# Sample data and server bootstrap


def _seed_sample_data(app: NewsfeedApplication) -> None:
    user_alex = app.create_user(locale="en_US", region="US", languages=["en"])
    user_wei = app.create_user(locale="zh_CN", region="CN", languages=["zh", "en"])

    app.upsert_interest({"user_id": user_alex.user_id, "type": "topic", "object_id": "technology", "weight": 0.9, "language": "en"})
    app.upsert_interest({"user_id": user_alex.user_id, "type": "topic", "object_id": "ai", "weight": 0.8, "language": "en"})
    app.upsert_interest({"user_id": user_wei.user_id, "type": "topic", "object_id": "economy", "weight": 0.7, "language": "zh"})
    app.upsert_interest({"user_id": user_wei.user_id, "type": "topic", "object_id": "technology", "weight": 0.6, "language": "zh"})

    now = datetime.now(timezone.utc)
    sample_items = [
        {
            "url": "https://news.example.com/ai-breakthrough",
            "title": "Major AI Breakthrough Announced",
            "summary": "Researchers unveil a new AI model that improves reasoning tasks.",
            "language": "en",
            "media_type": "text",
            "publish_ts": (now - timedelta(hours=2)).isoformat(),
            "publisher": "Daily Journal",
            "cluster_id": "cluster-ai-1",
            "source_quality": 0.85,
            "popularity": 0.8,
            "topics": [
                {"topic_id": "ai", "score": 0.9},
                {"topic_id": "technology", "score": 0.7},
            ],
        },
        {
            "url": "https://finance.example.cn/market-rebound",
            "title": "全球市场在政策利好下回暖",
            "summary": "多地市场在新的刺激政策下迎来显著反弹。",
            "language": "zh",
            "media_type": "text",
            "publish_ts": (now - timedelta(hours=5)).isoformat(),
            "publisher": "财经速递",
            "cluster_id": "cluster-econ-4",
            "source_quality": 0.75,
            "popularity": 0.65,
            "topics": [
                {"topic_id": "economy", "score": 0.85},
                {"topic_id": "markets", "score": 0.6},
            ],
        },
        {
            "url": "https://explore.example.com/startup-roundup",
            "title": "5 Startups to Watch This Week",
            "summary": "A curated list of early stage companies tackling climate tech and logistics.",
            "language": "en",
            "media_type": "text",
            "publish_ts": (now - timedelta(hours=20)).isoformat(),
            "publisher": "explore",
            "cluster_id": "cluster-explore-2",
            "source_quality": 0.55,
            "popularity": 0.35,
            "topics": [
                {"topic_id": "technology", "score": 0.6},
                {"topic_id": "climate", "score": 0.5},
            ],
        },
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Space Tourism Company Announces Affordable Flights",
            "summary": "Tickets to low orbit might soon cost less than a luxury cruise.",
            "language": "en",
            "media_type": "video",
            "publish_ts": (now - timedelta(hours=40)).isoformat(),
            "publisher": "Daily Journal",
            "cluster_id": "cluster-space-8",
            "source_quality": 0.8,
            "popularity": 0.55,
            "video_manifest_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "topics": [
                {"topic_id": "space", "score": 0.9},
                {"topic_id": "technology", "score": 0.5},
            ],
        },
        {
            "url": "https://news.example.com/election-update",
            "title": "Breaking: Election Commission Releases Turnout Figures",
            "summary": "Turnout hits a record high across multiple regions, prompting celebrations.",
            "language": "en",
            "media_type": "text",
            "publish_ts": (now - timedelta(minutes=30)).isoformat(),
            "publisher": "Daily Journal",
            "cluster_id": "cluster-politics-2",
            "source_quality": 0.82,
            "popularity": 0.9,
            "topics": [
                {"topic_id": "politics", "score": 0.8},
                {"topic_id": "breaking", "score": 0.7},
            ],
        },
    ]
    for entry in sample_items:
        app.ingest_item(entry)

    # Mark the latest item as breaking news.
    app.publish_breaking({"item_id": 5})


def run_server(host: str = "127.0.0.1", port: int = 8077) -> None:
    server = ThreadingHTTPServer((host, port), RequestHandler)
    _seed_sample_data(RequestHandler.app)
    print(f"Newsfeed service running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
