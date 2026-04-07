"""North America filter for GitHub README rows."""

from app.utils.geo_na import github_row_is_north_america


def test_keeps_us_state_location() -> None:
    assert github_row_is_north_america(
        "Dallas, TX",
        title="Intern",
        company="Co",
        description="",
    )


def test_keeps_sf_shorthand() -> None:
    assert github_row_is_north_america("SF", title="", company="", description="")


def test_drops_newcastle_uk() -> None:
    assert not github_row_is_north_america(
        "Newcastle upon Tyne, UK",
        title="Intern",
        company="",
        description="",
    )


def test_drops_london_uk() -> None:
    assert not github_row_is_north_america(
        "London, UK",
        title="Backend",
        company="Octopus",
        description="",
    )


def test_drops_uk_token_in_location() -> None:
    assert not github_row_is_north_america("UK", title="", company="", description="")


def test_keeps_canada_city() -> None:
    assert github_row_is_north_america(
        "Toronto, ON",
        title="",
        company="",
        description="",
    )


def test_drops_india_city() -> None:
    assert not github_row_is_north_america(
        "Bangalore",
        title="SWE",
        company="X",
        description="",
    )
