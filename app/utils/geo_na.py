"""North America geo gate for GitHub README rows (README lists worldwide internships)."""

from __future__ import annotations

import re

# US state / territory codes at end of "City, ST" (same idea as frontend Canada filter).
_US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT "
    "NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY DC".split()
)

# Canadian province / territory codes (2-letter) — not US states.
_CA_CODES = frozenset("ON BC AB QC MB SK NS NB PE NL YT NT NU".split())

# If any pattern matches, the row is **not** North America–focused for our product.
_NON_NA_PATTERNS: tuple[re.Pattern[str], ...] = (
    # United Kingdom / Ireland (strong)
    re.compile(
        r"(?i)(,\s*UK\s*$|\bUnited Kingdom\b|\bGreat Britain\b|Newcastle\s+upon\s+Tyne|"
        r",\s*England\s*$|,\s*Scotland\s*$|,\s*Wales\s*$|,\s*Northern Ireland\s*$|"
        r"London,\s*UK|Manchester,\s*UK|Birmingham,\s*UK|Liverpool,\s*UK|Leeds,\s*UK|"
        r"Bristol,\s*UK|Edinburgh,\s*Scotland|Glasgow,\s*Scotland|"
        r"Oxford,\s*England|Cambridge,\s*England|"
        r"Dublin,\s*Ireland|Cork,\s*Ireland|Galway,\s*Ireland|"
        r",\s*Ireland\s*$)",
    ),
    # EU / EEA (location line usually ends with country)
    re.compile(
        r"(?i)(,\s*Germany\s*$|,\s*France\s*$|,\s*Spain\s*$|,\s*Italy\s*$|,\s*Netherlands\s*$|"
        r",\s*Belgium\s*$|,\s*Austria\s*$|,\s*Sweden\s*$|,\s*Norway\s*$|,\s*Denmark\s*$|"
        r",\s*Finland\s*$|,\s*Poland\s*$|,\s*Portugal\s*$|,\s*Czech Republic\s*$|"
        r",\s*Switzerland\s*$|,\s*Greece\s*$|Berlin,\s*Germany|Munich,\s*Germany|"
        r"Paris,\s*France|Amsterdam,\s*Netherlands|Zurich,\s*Switzerland|"
        r"Stockholm,\s*Sweden|Warsaw,\s*Poland)",
    ),
    # South Asia / Oceania / East Asia hubs (internship tables)
    re.compile(
        r"(?i)(\bBangalore\b|\bBengaluru\b|Hyderabad|Mumbai|Pune|Chennai|Delhi,\s*India|"
        r",\s*India\s*$|,\s*Singapore\s*$|,\s*Japan\s*$|Tokyo|Seoul|"
        r",\s*Australia\s*$|Sydney,\s*NSW|Melbourne,\s*VIC)",
    ),
)


def _tail_state_code(line: str) -> str | None:
    m = re.search(r",\s*([A-Za-z]{2})\s*$", line.strip())
    if not m:
        return None
    return m.group(1).upper()


def _looks_north_american_location_line(loc: str) -> bool:
    """Heuristic: trailing ST is US state or CA province code."""
    s = loc.strip()
    if not s:
        return False
    code = _tail_state_code(s)
    if code and code in _US_STATE_CODES:
        return True
    if code and code in _CA_CODES:
        return True
    # Common NA city tokens without comma (README shorthand)
    if re.search(
        r"(?i)\b(SF|NYC|LA\b|Chicago|Seattle|Boston|Austin|Denver|Portland|Atlanta|"
        r"Toronto|Montreal|Vancouver|Calgary|Ottawa|Edmonton|Waterloo|Mexico City|Guadalajara|Monterrey)\b",
        s,
    ):
        return True
    if re.search(r"(?i)\b(Canada|United States|USA|U\.S\.A\.|Mexico)\b", s):
        return True
    # Canadian province names spelled out
    if re.search(
        r"(?i)\b(Ontario|Quebec|British Columbia|Alberta|Manitoba|Saskatchewan|"
        r"Nova Scotia|New Brunswick|Prince Edward Island|Newfoundland)\b",
        s,
    ):
        return True
    return False


def github_row_is_north_america(
    location: str,
    *,
    title: str = "",
    company: str = "",
    description: str = "",
) -> bool:
    """Return False if the README row clearly targets outside North America.

    Strategy (two-pass):
    1) Strong **exclude** patterns (UK/EU/APAC/India) on location + short context.
    2) Strong **include** heuristics for US/Canada/Mexico shorthands.
    3) If still ambiguous (e.g. ``Remote`` or unknown city), **keep** the row so we do not
       drop valid US internships; UK/EU rows are removed by (1).
    """
    loc = (location or "").strip()
    # Standalone country token in the Location column (README tables).
    if re.search(r"(?i)\bUK\b", loc):
        return False

    blob = "\n".join(
        [
            loc,
            (title or "").strip(),
            (company or "").strip(),
            (description or "")[:1200],
        ]
    )

    for rx in _NON_NA_PATTERNS:
        if rx.search(blob):
            return False

    if _looks_north_american_location_line(loc):
        return True

    # Remote / hybrid without geography: keep (majority of curated README are US employers).
    if re.search(r"(?i)\bremote\b|\bhybrid\b", loc):
        return True

    # Unknown single city without country — keep (cannot prove non-NA; rare UK without "UK")
    return True
