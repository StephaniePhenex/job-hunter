"""Parse curated GitHub README (markdown or HTML tables) into normalized jobs."""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.utils.geo_na import github_row_is_north_america
from app.utils.schemas import JobNormalized

logger = logging.getLogger(__name__)

_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [p.strip() for p in line.split("|")]


def _first_apply_url_from_td(td) -> str:
    """First non-image job/application link in Application column."""
    for a in td.find_all("a", href=True):
        h = (a.get("href") or "").strip()
        if not h.startswith("http"):
            continue
        if "imgur.com" in h or h.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            continue
        return h
    return ""


def _parse_html_readme_tables(html: str) -> list[JobNormalized]:
    """SimplifyJobs-style README: HTML <table> with Company / Role / Location / Application."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[JobNormalized] = []
    posted = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for table in soup.find_all("table"):
        thead = table.find("thead")
        tbody = table.find("tbody")
        if not thead or not tbody:
            continue
        headers = [th.get_text(strip=True).lower() for th in thead.find_all("th")]
        joined = " ".join(headers)
        if "company" not in joined or "role" not in joined:
            continue

        last_company = ""
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            raw_co = tds[0].get_text(strip=True)
            if not raw_co or raw_co in ("↳", "↵") or raw_co.startswith("↳"):
                company = last_company
            else:
                last_company = raw_co
                company = raw_co

            title = tds[1].get_text(strip=True)
            location = tds[2].get_text(strip=True)
            url = _first_apply_url_from_td(tds[3])

            if not title and not company:
                continue
            if not url:
                continue

            description = " | ".join(
                p
                for p in (
                    f"Company: {company}" if company else "",
                    f"Role: {title}" if title else "",
                    f"Location: {location}" if location else "",
                )
                if p
            )
            out.append(
                JobNormalized(
                    title=title or "Internship",
                    company=company or "Unknown",
                    location=location,
                    url=url,
                    description=description,
                    posted_at=posted,
                    source="github",
                )
            )

    return out


def _parse_markdown_table(md: str) -> list[JobNormalized]:
    """Extract internship rows from pittcsc-style pipe README tables."""
    lines = md.splitlines()
    header_line_idx: int | None = None
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        low = line.lower()
        if "company" in low and ("role" in low or "position" in low):
            header_line_idx = i
            break
    if header_line_idx is None:
        return []

    header_cells = _split_row(lines[header_line_idx])

    def col_index(sub: str) -> int | None:
        for idx, h in enumerate(header_cells):
            if sub.lower() in h.lower():
                return idx
        return None

    ci_company = col_index("company")
    ci_role = col_index("role")
    if ci_role is None:
        ci_role = col_index("position")
    ci_loc = col_index("location")
    ci_app = col_index("application")
    if ci_app is None:
        ci_app = col_index("apply")

    out: list[JobNormalized] = []
    for line in lines[header_line_idx + 1 :]:
        line = line.strip()
        if not line.startswith("|"):
            continue
        if re.match(r"^\|\s*-+", line):
            continue
        parts = _split_row(line)
        used = [x for x in [ci_company, ci_role, ci_loc, ci_app] if x is not None]
        if not used:
            continue
        max_idx = max(used)
        if max_idx >= len(parts):
            continue

        def get_cell(idx: int | None) -> str:
            if idx is None or idx >= len(parts):
                return ""
            return parts[idx]

        company = get_cell(ci_company)
        title = get_cell(ci_role)
        location = get_cell(ci_loc)
        app_cell = get_cell(ci_app)

        url = ""
        m = _LINK_RE.search(app_cell)
        if m:
            url = m.group(2).strip()
        elif app_cell.startswith("http"):
            url = app_cell.split()[0]

        if not title and not company:
            continue
        if not url:
            continue

        extra_parts = [
            p
            for i, p in enumerate(parts)
            if i not in {ci_company, ci_role, ci_loc, ci_app}
            and p.strip()
            and not p.strip().startswith("http")
        ]
        extra_text = " | ".join(
            _LINK_RE.sub(r"\1", p).strip() for p in extra_parts if p.strip()
        )
        description_parts = [
            f"Company: {company}" if company else "",
            f"Role: {title}" if title else "",
            f"Location: {location}" if location else "",
            f"Notes: {extra_text}" if extra_text else "",
        ]
        description = " | ".join(p for p in description_parts if p)

        out.append(
            JobNormalized(
                title=title or "Internship",
                company=company or "Unknown",
                location=location,
                url=url,
                description=description,
                posted_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source="github",
            )
        )
    return out


def _parse_readme(text: str) -> list[JobNormalized]:
    """Prefer HTML tables (current SimplifyJobs README), else markdown pipes."""
    if "<table" in text.lower() and "<thead>" in text.lower():
        html_jobs = _parse_html_readme_tables(text)
        if html_jobs:
            return html_jobs
    return _parse_markdown_table(text)


async def fetch_jobs() -> list[JobNormalized]:
    """Download README from configured URL and parse tables."""
    settings = get_settings()
    url = str(settings.github_internships_readme_url)
    cap = max(1, settings.github_internships_max_rows)
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            text = r.text
    except Exception:
        logger.exception("GitHub README fetch failed: %s", url)
        return []

    raw = _parse_readme(text)
    jobs = [
        j
        for j in raw
        if github_row_is_north_america(
            j.location,
            title=j.title,
            company=j.company,
            description=j.description,
        )
    ][:cap]
    dropped = len(raw) - len(jobs)
    if dropped:
        logger.info(
            "GitHub README: dropped %s non–North America rows; keeping %s (cap=%s)",
            dropped,
            len(jobs),
            cap,
        )
    else:
        logger.info("GitHub README: parsed %s NA rows (cap=%s) from %s", len(jobs), cap, url)
    return jobs


class GitHubInternshipsScraper:
    """Wrapper implementing JobScraper."""

    source = "github"

    async def fetch_jobs(self) -> list[JobNormalized]:
        return await fetch_jobs()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    jobs_async = asyncio.run(fetch_jobs())
    for j in jobs_async[:5]:
        print(j.model_dump())
