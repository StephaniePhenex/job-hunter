"""URL normalization for applied-url keys."""

from app.utils.url_norm import normalize_application_url


def test_host_case_insensitive() -> None:
    a = normalize_application_url("HTTPS://Example.COM/path/")
    b = normalize_application_url("https://example.com/path")
    assert a == b


def test_query_order_normalized() -> None:
    a = normalize_application_url("https://x.com/a?z=1&y=2")
    b = normalize_application_url("https://x.com/a?y=2&z=1")
    assert a == b
