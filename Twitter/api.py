"""
Lightweight REST API over the TwitterService for demonstration purposes.

Requires clients to send the `X-API-Key` header. A simple token bucket keeps
traffic per API key within configurable bounds.

Endpoints (JSON):
- POST /users {screen_name}
- POST /follow {follower_id, followee_id}
- POST /tweets {author_id, text}
- GET  /timeline/{user_id}?limit=&cursor=
- POST /tweets/{tweet_id}/like
- POST /tweets/{tweet_id}/retweet

Run with: `uvicorn Twitter.api:app --reload`
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, constr

from .prototype import Tweet, TwitterService

service = TwitterService()
app = FastAPI(title="Twitter Prototype API", version="0.1.0")

DEFAULT_API_KEY = os.getenv("TWITTER_API_KEY", "dev-token")


def _load_api_keys() -> frozenset[str]:
    keys_env = os.getenv("TWITTER_API_KEYS")
    if keys_env:
        keys = {key.strip() for key in keys_env.split(",")}
    else:
        keys = {DEFAULT_API_KEY}
    return frozenset(filter(None, keys))


API_KEYS: frozenset[str] = _load_api_keys()
JWT_SECRET = os.getenv("TWITTER_JWT_SECRET")
RATE_LIMIT = int(os.getenv("TWITTER_RATE_LIMIT", "60"))
RATE_WINDOW_SECONDS = int(os.getenv("TWITTER_RATE_WINDOW_SECONDS", "60"))

_rate_lock = threading.Lock()
_rate_counters: Dict[str, Deque[float]] = defaultdict(deque)


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _validate_jwt(token: str) -> Tuple[str, str]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise AuthError("invalid JWT structure") from exc

    try:
        header = json.loads(_base64url_decode(header_b64))
        payload = json.loads(_base64url_decode(payload_b64))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AuthError("invalid JWT encoding") from exc

    if header.get("alg") != "HS256":
        raise AuthError("unsupported JWT algorithm")
    if JWT_SECRET is None:
        raise AuthError("JWT secret not configured")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(JWT_SECRET.encode(), signing_input, "sha256").digest()
    provided_sig = _base64url_decode(signature_b64)

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise AuthError("invalid JWT signature")

    exp = payload.get("exp")
    if exp is not None and time.time() > float(exp):
        raise AuthError("JWT expired")
    subject = payload.get("sub")
    if not subject:
        raise AuthError("JWT missing subject")
    return subject, payload.get("scope", "")


def authorize(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    auth_header = request.headers.get("authorization")
    identity: Optional[str] = None

    if api_key:
        if api_key not in API_KEYS:
            raise AuthError("invalid API key")
        identity = f"key:{api_key}"
    elif auth_header:
        if not auth_header.lower().startswith("bearer "):
            raise AuthError("unsupported authorization scheme")
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or not parts[1]:
            raise AuthError("missing bearer token")
        token = parts[1]
        subject, _ = _validate_jwt(token)
        identity = f"user:{subject}"
    else:
        raise AuthError("missing credentials")

    now = time.time()
    with _rate_lock:
        history = _rate_counters[identity]
        while history and now - history[0] > RATE_WINDOW_SECONDS:
            history.popleft()
        if len(history) >= RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded",
            )
        history.append(now)
    return identity


class CreateUserRequest(BaseModel):
    screen_name: constr(min_length=1, max_length=32)


class CreateUserResponse(BaseModel):
    id: str
    screen_name: str


class FollowRequest(BaseModel):
    follower_id: str
    followee_id: str


class CreateTweetRequest(BaseModel):
    author_id: str
    text: constr(min_length=1, max_length=280)


class TweetResponse(BaseModel):
    id: str
    author_id: str
    text: str
    created_at: str
    like_count: int
    retweet_count: int

    @classmethod
    def from_model(cls, tweet: Tweet) -> "TweetResponse":
        return cls(
            id=tweet.id,
            author_id=tweet.author_id,
            text=tweet.text,
            created_at=tweet.created_at.isoformat(),
            like_count=tweet.like_count,
            retweet_count=tweet.retweet_count,
        )


class TimelineResponse(BaseModel):
    tweets: List[TweetResponse]
    next_cursor: Optional[str]


@app.post("/users", response_model=CreateUserResponse, dependencies=[Depends(authorize)])
def create_user(payload: CreateUserRequest) -> CreateUserResponse:
    user = service.register_user(payload.screen_name)
    return CreateUserResponse(id=user.id, screen_name=user.screen_name)


@app.post("/follow", status_code=204, dependencies=[Depends(authorize)])
def follow(payload: FollowRequest) -> None:
    try:
        service.follow(payload.follower_id, payload.followee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/follow", status_code=204, dependencies=[Depends(authorize)])
def unfollow(payload: FollowRequest) -> None:
    try:
        service.unfollow(payload.follower_id, payload.followee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/tweets", response_model=TweetResponse, dependencies=[Depends(authorize)])
def create_tweet(payload: CreateTweetRequest) -> TweetResponse:
    try:
        tweet = service.post_tweet(payload.author_id, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TweetResponse.from_model(tweet)


@app.get("/timeline/{user_id}", response_model=TimelineResponse, dependencies=[Depends(authorize)])
def get_timeline(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = None,
) -> TimelineResponse:
    try:
        tweets, next_cursor = service.get_home_timeline(user_id, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TimelineResponse(
        tweets=[TweetResponse.from_model(tweet) for tweet in tweets],
        next_cursor=next_cursor,
    )


@app.post("/tweets/{tweet_id}/like", response_model=TweetResponse, dependencies=[Depends(authorize)])
def like_tweet(tweet_id: str) -> TweetResponse:
    try:
        tweet = service.like_tweet("anonymous", tweet_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TweetResponse.from_model(tweet)


@app.post("/tweets/{tweet_id}/retweet", response_model=TweetResponse, dependencies=[Depends(authorize)])
def retweet(tweet_id: str) -> TweetResponse:
    try:
        tweet = service.retweet("anonymous", tweet_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TweetResponse.from_model(tweet)
