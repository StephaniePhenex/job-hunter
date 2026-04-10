"""Focus role keyword gate."""

from app.utils.role_keywords import (
    count_focus_group_hits,
    passes_focus_role_keywords,
    priority_from_focus_group_hits,
)


def test_priority_tiers() -> None:
    assert priority_from_focus_group_hits(0) == "LOW"
    assert priority_from_focus_group_hits(1) == "LOW"
    assert priority_from_focus_group_hits(2) == "MEDIUM"
    assert priority_from_focus_group_hits(3) == "MEDIUM"
    assert priority_from_focus_group_hits(4) == "HIGH"


def test_count_multiple_groups() -> None:
    blob_title = "Web3 Developer"
    blob_desc = "Also product engineer and DevRel"
    n = count_focus_group_hits(blob_title, "", blob_desc)
    assert n >= 3


def test_accepts_web3() -> None:
    assert passes_focus_role_keywords(title="Web3 Developer Intern", company="X", description="")


def test_accepts_full_stack_ai_saas() -> None:
    assert passes_focus_role_keywords(
        title="Full Stack Engineer (AI/SaaS)",
        company="Acme",
        description="",
    )


def test_accepts_devrel() -> None:
    assert passes_focus_role_keywords(
        title="Developer Relations",
        company="",
        description="DevRel for our API",
    )


def test_rejects_generic_construction() -> None:
    assert not passes_focus_role_keywords(
        title="Construction Labourer",
        company="BuildCo",
        description="On-site work",
    )


def test_accepts_media_engineer() -> None:
    assert passes_focus_role_keywords(
        title="Media Engineer",
        company="Studio",
        description="Broadcast systems",
    )


def test_accepts_software_engineer_title() -> None:
    assert passes_focus_role_keywords(
        title="Software Engineer Intern",
        company="Co",
        description="",
    )


def test_accepts_fuzzy_software_developer_titles() -> None:
    """Synonym phrases (engineering/developer/intern) must pass the same gate."""
    cases = [
        ("Software Engineering Intern", "", ""),
        ("Software Developer Intern", "", ""),
        ("Junior Software Developer", "", ""),
        ("Full Stack Developer", "", ""),
        ("Full-Stack Developer Intern", "", ""),
        ("Developer Intern", "", "General internship building internal tools."),
    ]
    for title, company, desc in cases:
        assert passes_focus_role_keywords(
            title=title, company=company, description=desc
        ), f"expected pass: {title!r}"


def test_accepts_technical_content_engineer() -> None:
    assert passes_focus_role_keywords(
        title="Technical Content Engineer",
        company="",
        description="",
    )


def test_accepts_animation_vfx_games() -> None:
    assert passes_focus_role_keywords(
        title="VFX - Sledgehammer Games Internships (May 2026)",
        company="",
        description="",
    )


def test_accepts_digital_marketing_internship() -> None:
    assert passes_focus_role_keywords(
        title="Digital Marketing, RPM Internship (Rolling Intake)",
        company="",
        description="",
    )


def test_accepts_electrical_engineering_internship() -> None:
    assert passes_focus_role_keywords(
        title="Electrical engineering internship - Resources (Jun 2026)",
        company="",
        description="",
    )
