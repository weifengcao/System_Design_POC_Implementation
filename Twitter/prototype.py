"""
Simplified Twitter prototype demonstrating core concepts from the design doc.

The implementation focuses on:
- User graph management (follow/unfollow).
- Tweet creation with fan-out-on-write for regular users.
- Fan-in-on-read for high-follower (celebrity) accounts to avoid mass fan-out.
- Timeline retrieval with cursors (simple timestamp-based pagination).

In production these abstractions would be replaced with distributed stores,
durable messaging, and service boundaries. Here we use in-memory dictionaries
for clarity and determinism.
"""

from __future__ import annotations

import bisect
import dataclasses
import datetime as dt
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple

# Tunables kept small for the demo; production values would be far higher.
MAX_TIMELINE_LENGTH = 800
CELEBRITY_FOLLOWER_THRESHOLD = 50_000
MAX_TWEETS_PER_AUTHOR_CACHE = 1_000


@dataclass(frozen=True)
class Tweet:
    id: str
    author_id: str
    text: str
    created_at: dt.datetime
    like_count: int = 0
    retweet_count: int = 0


@dataclass
class User:
    id: str
    screen_name: str
    followees: Set[str] = field(default_factory=set)
    followers: Set[str] = field(default_factory=set)
    is_celeb: bool = False

    def update_celebrity_flag(self) -> None:
        self.is_celeb = len(self.followers) >= CELEBRITY_FOLLOWER_THRESHOLD


class GraphStore:
    """In-memory social graph. Thread-safe for the demo."""

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        self._lock = threading.RLock()

    def create_user(self, screen_name: str) -> User:
        with self._lock:
            user_id = uuid.uuid4().hex
            user = User(id=user_id, screen_name=screen_name)
            self._users[user_id] = user
            return user

    def get_user(self, user_id: str) -> User:
        try:
            return self._users[user_id]
        except KeyError as exc:
            raise ValueError(f"user {user_id} not found") from exc

    def follow(self, follower_id: str, followee_id: str) -> None:
        if follower_id == followee_id:
            raise ValueError("users cannot follow themselves")
        with self._lock:
            follower = self.get_user(follower_id)
            followee = self.get_user(followee_id)
            if followee_id in follower.followees:
                return
            follower.followees.add(followee_id)
            followee.followers.add(follower_id)
            followee.update_celebrity_flag()

    def unfollow(self, follower_id: str, followee_id: str) -> None:
        with self._lock:
            follower = self.get_user(follower_id)
            followee = self.get_user(followee_id)
            follower.followees.discard(followee_id)
            followee.followers.discard(follower_id)
            followee.update_celebrity_flag()

    def followers(self, user_id: str) -> Set[str]:
        return set(self.get_user(user_id).followers)

    def followees(self, user_id: str) -> Set[str]:
        return set(self.get_user(user_id).followees)


class TimelineStore:
    """Stores per-user timelines with bounded size."""

    def __init__(self) -> None:
        self._timelines: Dict[str, Deque[Tuple[dt.datetime, str]]] = defaultdict(deque)
        self._lock = threading.RLock()

    def push(self, user_id: str, tweet: Tweet) -> None:
        with self._lock:
            timeline = self._timelines[user_id]
            timeline.appendleft((tweet.created_at, tweet.id))
            while len(timeline) > MAX_TIMELINE_LENGTH:
                timeline.pop()

    def remove(self, user_id: str, tweet_id: str) -> None:
        with self._lock:
            timeline = self._timelines[user_id]
            self._timelines[user_id] = deque(
                entry for entry in timeline if entry[1] != tweet_id
            )

    def slice(
        self,
        user_id: str,
        limit: int,
        cursor: Optional[dt.datetime] = None,
    ) -> List[str]:
        with self._lock:
            timeline = self._timelines[user_id]
            if cursor is None:
                return [tweet_id for _, tweet_id in list(timeline)[:limit]]
            # Find first entry older than cursor
            result: List[str] = []
            for created_at, tweet_id in timeline:
                if created_at < cursor:
                    result.append(tweet_id)
                if len(result) == limit:
                    break
            return result


class TweetStore:
    """Primary tweet storage. Uses sorted list for author lookups."""

    def __init__(self) -> None:
        self._tweets: Dict[str, Tweet] = {}
        self._tweets_by_author: Dict[str, List[Tuple[dt.datetime, str]]] = defaultdict(list)
        self._lock = threading.RLock()

    def create(self, author_id: str, text: str) -> Tweet:
        tweet_id = uuid.uuid4().hex
        now = dt.datetime.now(dt.timezone.utc)
        tweet = Tweet(id=tweet_id, author_id=author_id, text=text, created_at=now)
        with self._lock:
            self._tweets[tweet_id] = tweet
            author_index = self._tweets_by_author[author_id]
            bisect.insort(author_index, (-now.timestamp(), tweet_id))
            if len(author_index) > MAX_TWEETS_PER_AUTHOR_CACHE:
                author_index.pop()
        return tweet

    def get(self, tweet_id: str) -> Tweet:
        try:
            return self._tweets[tweet_id]
        except KeyError as exc:
            raise ValueError(f"tweet {tweet_id} not found") from exc

    def recent_by_author(self, author_id: str, limit: int) -> List[Tweet]:
        with self._lock:
            entries = self._tweets_by_author.get(author_id, [])
            tweet_ids = [tweet_id for _, tweet_id in entries[:limit]]
        return [self._tweets[tid] for tid in tweet_ids]

    def like(self, tweet_id: str) -> Tweet:
        with self._lock:
            tweet = dataclasses.replace(self._tweets[tweet_id], like_count=self._tweets[tweet_id].like_count + 1)
            self._tweets[tweet_id] = tweet
            return tweet

    def retweet(self, tweet_id: str) -> Tweet:
        with self._lock:
            tweet = dataclasses.replace(
                self._tweets[tweet_id],
                retweet_count=self._tweets[tweet_id].retweet_count + 1,
            )
            self._tweets[tweet_id] = tweet
            return tweet


class TwitterService:
    """Coordinates timeline fan-out / fan-in along with user and tweet storage."""

    def __init__(self) -> None:
        self.graph = GraphStore()
        self.tweet_store = TweetStore()
        self.timeline_store = TimelineStore()
        self._lock = threading.RLock()

    def register_user(self, screen_name: str) -> User:
        return self.graph.create_user(screen_name)

    def follow(self, follower_id: str, followee_id: str) -> None:
        self.graph.follow(follower_id, followee_id)

    def unfollow(self, follower_id: str, followee_id: str) -> None:
        self.graph.unfollow(follower_id, followee_id)

    def post_tweet(self, author_id: str, text: str) -> Tweet:
        if len(text) > 280:
            raise ValueError("tweet exceeds 280 characters")
        tweet = self.tweet_store.create(author_id, text)
        followers = self.graph.followers(author_id)
        author = self.graph.get_user(author_id)
        if not author.is_celeb:
            # Fan-out on write for normal users.
            for follower_id in followers:
                self.timeline_store.push(follower_id, tweet)
        # Authors always see their own tweets first.
        self.timeline_store.push(author_id, tweet)
        return tweet

    def get_home_timeline(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Tweet], Optional[str]]:
        cursor_dt = (
            dt.datetime.fromisoformat(cursor) if cursor is not None else None
        )
        tweet_ids = self.timeline_store.slice(user_id, limit, cursor_dt)
        tweets = [self.tweet_store.get(tid) for tid in tweet_ids]
        # Merge celebrity followees lazily by fetching their recent tweets.
        missing = limit - len(tweets)
        if missing > 0:
            celeb_tweets = self._merge_celeb_tweets(user_id, cursor_dt, missing)
            tweets.extend(celeb_tweets)
            tweets.sort(key=lambda t: t.created_at, reverse=True)
            tweets = tweets[:limit]
        next_cursor = tweets[-1].created_at.isoformat() if tweets else None
        return tweets, next_cursor

    def _merge_celeb_tweets(
        self,
        user_id: str,
        cursor_dt: Optional[dt.datetime],
        limit: int,
    ) -> List[Tweet]:
        celeb_ids = [
            uid
            for uid in self.graph.followees(user_id)
            if self.graph.get_user(uid).is_celeb
        ]
        candidate_tweets: List[Tweet] = []
        for celeb_id in celeb_ids:
            tweets = self.tweet_store.recent_by_author(celeb_id, limit * 2)
            for tweet in tweets:
                if cursor_dt is None or tweet.created_at < cursor_dt:
                    candidate_tweets.append(tweet)
        candidate_tweets.sort(key=lambda t: t.created_at, reverse=True)
        return candidate_tweets[:limit]

    def like_tweet(self, user_id: str, tweet_id: str) -> Tweet:
        # In a full system we would track who liked which tweet; omitted here.
        return self.tweet_store.like(tweet_id)

    def retweet(self, user_id: str, tweet_id: str) -> Tweet:
        return self.tweet_store.retweet(tweet_id)


def _demo() -> None:
    service = TwitterService()
    alice = service.register_user("alice")
    bob = service.register_user("bob")
    celeb = service.register_user("celebrity")

    # Artificially promote celeb to celebrity status for the demo.
    celeb.followers = {uuid.uuid4().hex for _ in range(CELEBRITY_FOLLOWER_THRESHOLD)}
    celeb.update_celebrity_flag()

    service.follow(alice.id, bob.id)
    service.follow(alice.id, celeb.id)

    service.post_tweet(bob.id, "hello from bob")
    service.post_tweet(celeb.id, "exclusive update")

    tweets, cursor = service.get_home_timeline(alice.id, limit=5)
    print("Alice timeline:")
    for tweet in tweets:
        print(f"- @{tweet.author_id[:4]}… {tweet.text} ({tweet.created_at.isoformat()})")
    print("Next cursor:", cursor)


if __name__ == "__main__":
    _demo()
