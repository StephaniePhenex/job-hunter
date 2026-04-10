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


def test_joins_multiple_json_ld_job_locations() -> None:
    html = """
    <!DOCTYPE html>
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"JobPosting",
     "title":"Intern",
     "jobLocation":[
       {"@type":"Place","address":{"addressLocality":"Toronto","addressRegion":"ON","addressCountry":"CA"}},
       {"@type":"Place","address":{"addressLocality":"Vancouver","addressRegion":"BC","addressCountry":"CA"}}
 ]}
    </script>
    </head><body></body></html>
    """
    loc = extract_location_from_job_html(html)
    assert "Toronto" in loc
    assert "Vancouver" in loc
    assert "; " in loc


def test_normalizes_glued_location_tokens() -> None:
    from app.utils.job_location_html import _normalize_mangled_location_text

    assert "Texas" in _normalize_mangled_location_text("WashingtonTexasArizona")
    assert "FL South" in _normalize_mangled_location_text("Miami, FLSouth Carolina")
    norm = _normalize_mangled_location_text("Atlanta, GANew York, NYRemote in USA")
    assert "GA New" in norm
    assert "NY Remote" in norm or ", NY Remote" in norm
