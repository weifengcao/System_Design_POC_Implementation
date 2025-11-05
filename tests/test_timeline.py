from __future__ import annotations

import uuid

from Twitter.prototype import (
    CELEBRITY_FOLLOWER_THRESHOLD,
    TwitterService,
)


def test_fan_out_for_regular_user():
    service = TwitterService()
    alice = service.register_user("alice")
    bob = service.register_user("bob")
    service.follow(alice.id, bob.id)

    tweet = service.post_tweet(bob.id, "hello from bob")
    timeline, _ = service.get_home_timeline(alice.id, limit=10)

    assert any(item.id == tweet.id for item in timeline)


def test_fan_in_for_celeb_user():
    service = TwitterService()
    follower = service.register_user("follower")
    celeb = service.register_user("celeb")
    service.follow(follower.id, celeb.id)

    celeb_user = service.graph.get_user(celeb.id)
    celeb_user.followers.update({str(uuid.uuid4()) for _ in range(CELEBRITY_FOLLOWER_THRESHOLD)})
    celeb_user.update_celebrity_flag()

    tweet = service.post_tweet(celeb.id, "breaking news")
    timeline, _ = service.get_home_timeline(follower.id, limit=10)

    assert any(item.id == tweet.id for item in timeline)
    assert service.graph.get_user(celeb.id).is_celeb is True
