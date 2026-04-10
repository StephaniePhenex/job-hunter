"""Extract human-readable job location from public job posting HTML (JSON-LD JobPosting first)."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

# Match frontend Canada filter: 2-letter region codes (US states + DC vs Canadian provinces).
_US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT "
    "NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY DC".split()
)
_CA_PROV_CODES = frozenset("ON BC AB QC MB SK NS NB PE NL YT NT NU".split())


def _normalize_mangled_location_text(s: str) -> str:
    """Insert spaces for glued tokens (camelCase, ', FLSouth', ', GANew York', ', NYRemote')."""
    if not s:
        return s
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    glued = re.compile(r",\s*([A-Za-z]{2})([A-Z][a-z]+)")

    def _fix_after_comma_code(m: re.Match[str]) -> str:
        code, word = m.group(1), m.group(2)
        c = code.upper()
        if c in _CA_PROV_CODES:
            return m.group(0)
        if c in _US_STATE_CODES:
            return f", {c} {word}"
        return m.group(0)

    for _ in range(16):
        next_t = glued.sub(_fix_after_comma_code, t)
        if next_t == t:
            break
        t = next_t
    return t


def _join_address(addr: dict[str, Any]) -> str:
    if not isinstance(addr, dict):
        return ""
    locality = (addr.get("addressLocality") or "").strip()
    region = (addr.get("addressRegion") or "").strip()
    country = (addr.get("addressCountry") or "").strip()
    # Sometimes region is a full name
    parts = [p for p in (locality, region, country) if p]
    return ", ".join(parts)[:512]


def _location_from_jobposting(obj: dict[str, Any]) -> str:
    loc = obj.get("jobLocation")
    candidates: list[str] = []

    def one_block(block: Any) -> None:
        if isinstance(block, dict):
            if block.get("name"):
                candidates.append(str(block["name"]).strip()[:512])
            addr = block.get("address")
            if isinstance(addr, dict):
                s = _join_address(addr)
                if s:
                    candidates.append(s)
            # Some sites nest Place without address
            if isinstance(addr, str) and addr.strip():
                candidates.append(addr.strip()[:512])
        elif isinstance(block, str) and block.strip():
            candidates.append(block.strip()[:512])

    if isinstance(loc, list):
        for item in loc:
            one_block(item)
    else:
        one_block(loc)

    best: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        raw = str(c).strip()
        if not raw:
            continue
        low = raw.lower()
        if len(raw) > 3 and low not in ("canada", "united states", "usa"):
            key = re.sub(r"\s+", " ", low)
            if key not in seen:
                seen.add(key)
                best.append(raw[:512])
    if best:
        return _normalize_mangled_location_text("; ".join(best)[:512])
    if candidates:
        return _normalize_mangled_location_text(str(candidates[0]).strip()[:512])
    return ""


def _walk_for_jobposting(obj: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        t = obj.get("@type")
        types = t if isinstance(t, list) else ([t] if t else [])
        if any(isinstance(x, str) and x.lower() == "jobposting" for x in types):
            out.append(obj)
        for v in obj.values():
            _walk_for_jobposting(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_for_jobposting(item, out)


def _parse_json_ld_scripts(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        st = (script.get("type") or "").lower()
        if "ld+json" not in st:
            continue
        raw = (script.string or script.get_text() or "").strip()
        if not raw or "JobPosting" not in raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        found: list[dict[str, Any]] = []
        _walk_for_jobposting(data, found)
        for jp in found:
            loc = _location_from_jobposting(jp)
            if loc:
                return loc
    return ""


def _regex_fallback(html: str) -> str:
    """Loose patterns when JSON-LD is missing (Prosple / TalentEgg style)."""
    # Visible "Location" label
    m = re.search(
        r"(?is)<[^>]*>\s*Location\s*</[^>]+>\s*<[^>]+>\s*([^<]{3,200})",
        html,
    )
    if m:
        return _normalize_mangled_location_text(re.sub(r"\s+", " ", m.group(1)).strip()[:512])
    m = re.search(
        r"(?i)Location\s*:\s*([^\n<]{3,200})",
        html,
    )
    if m:
        return _normalize_mangled_location_text(re.sub(r"\s+", " ", m.group(1)).strip()[:512])
    return ""


def extract_location_from_job_html(html: str) -> str:
    """Return best-effort location string, or empty if not found."""
    if not html or len(html) < 50:
        return ""
    loc = _parse_json_ld_scripts(html)
    if loc:
        return loc
    return _regex_fallback(html)
