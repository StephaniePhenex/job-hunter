"""Eluta HTML parsing (no live network)."""

from app.scrapers.eluta import (
    _job_url_from_data_attr,
    _list_url_with_page,
    parse_organic_jobs,
)

LIST_HTML = """
<div id="organic-jobs">
  <div data-url="spl/test-job-abc123?imo=1" class="organic-job odd">
    <h2 class="title">
      <a class="lk-job-title" href="#!" title="Senior Python Developer">Senior Python Developer</a>
    </h2>
    <a class="employer lk-employer" href="#!">Acme Corp</a>
    <span class="location"><span>Toronto ON</span></span>
    <span class="description">Build APIs and <span class="highlight">Python</span> services.</span>
    <a class="lk lastseen" href="#!">1 day ago</a>
  </div>
</div>
"""


def test_parse_organic_jobs_extracts_fields() -> None:
    rows = parse_organic_jobs(LIST_HTML)
    assert len(rows) == 1
    r = rows[0]
    assert r["title"] == "Senior Python Developer"
    assert r["company"] == "Acme Corp"
    assert r["location"] == "Toronto ON"
    assert "Python" in r["description"]
    assert r["posted_at"] == "1 day ago"
    assert r["url"].startswith("https://www.eluta.ca/")
    assert "spl/test-job-abc123" in r["url"]


def test_job_url_from_data_attr() -> None:
    assert _job_url_from_data_attr("spl/x-y-z?imo=1") == "https://www.eluta.ca/spl/x-y-z?imo=1"


def test_list_url_with_page() -> None:
    base = "https://www.eluta.ca/Software-Engineer-jobs"
    assert _list_url_with_page(base, 1) == base
    assert _list_url_with_page(base, 2) == base + "?pg=2"
    base_q = "https://www.eluta.ca/search?q=test"
    assert _list_url_with_page(base_q, 2) == base_q + "&pg=2"
