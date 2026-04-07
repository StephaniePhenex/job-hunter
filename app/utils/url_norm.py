"""Canonical job application URL for cross-scan applied-state matching."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_application_url(url: str) -> str:
    """Stable key: scheme + host lowercased, trim path trailing slash, drop fragment.

    Query string order is normalized (sorted by key) so equivalent URLs match.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    p = urlparse(raw)
    # Bare "host.com/path" → netloc empty; treat as https URL
    if not p.netloc and p.path and "://" not in raw.split("/", 1)[0]:
        p = urlparse("https://" + raw.lstrip("/"))

    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()
    if not netloc and p.path.startswith("//"):
        inner = urlparse("https:" + raw if "://" not in raw[:12] else raw)
        scheme = (inner.scheme or "https").lower()
        netloc = (inner.netloc or "").lower()
        path = inner.path or ""
        query = inner.query
    else:
        path = p.path or ""
        query = p.query

    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    if query:
        pairs = parse_qsl(query, keep_blank_values=True)
        pairs.sort(key=lambda x: (x[0], x[1]))
        query = urlencode(pairs)

    return urlunparse((scheme, netloc, path, "", query, ""))
