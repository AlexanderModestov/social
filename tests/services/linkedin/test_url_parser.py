import pytest
from bot.services.linkedin.url_parser import parse_linkedin_url, build_parent_comment_urn


def test_activity_post_url():
    p = parse_linkedin_url(
        "https://www.linkedin.com/posts/jane_activity-7448808898326654978-iW20"
    )
    assert p["post_urn"] == "urn:li:activity:7448808898326654978"
    assert p["post_activity_id"] == "7448808898326654978"
    assert p["url_type"] == "post"


def test_share_post_url():
    p = parse_linkedin_url(
        "https://www.linkedin.com/posts/ivan_one-broker-share-7449499107418669056-ZYt7"
    )
    assert p["post_urn"] == "urn:li:share:7449499107418669056"
    assert p["url_type"] == "post"


def test_comment_url_extracts_post_and_comment():
    p = parse_linkedin_url(
        "https://www.linkedin.com/feed/update/urn:li:activity:7448387840113184768"
        "?commentUrn=urn%3Ali%3Acomment%3A%28activity%3A7448387840113184768"
        "%2C7449095071892672512%29"
    )
    assert p["url_type"] == "comment"
    assert p["post_urn"] == "urn:li:activity:7448387840113184768"
    assert p["comment_id"] == "7449095071892672512"


def test_unknown_url():
    assert parse_linkedin_url("https://example.com/foo")["url_type"] == "unknown"


def test_build_parent_comment_urn():
    urn = build_parent_comment_urn("urn:li:activity:123", "456")
    assert urn == "urn:li:comment:(urn:li:activity:123,456)"
