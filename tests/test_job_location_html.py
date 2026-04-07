"""JSON-LD JobPosting location extraction."""

from app.utils.job_location_html import extract_location_from_job_html


def test_extracts_json_ld_job_location() -> None:
    html = """
    <!DOCTYPE html>
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting",
     "title":"Intern","jobLocation":{"@type":"Place",
      "address":{"addressLocality":"Calgary","addressRegion":"AB","addressCountry":"CA"}}}
    </script>
    </head><body></body></html>
    """
    loc = extract_location_from_job_html(html)
    assert "Calgary" in loc
    assert "AB" in loc
