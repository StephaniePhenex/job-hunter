"""Hardcoded user profile for relevance scoring (MVP)."""

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Target intern seeker preferences (Canada, Fall, interests)."""

    location_focus: str = Field(
        default="Canada",
        description="Geographic focus",
    )
    term: str = Field(
        default="Fall internship",
        description="Preferred internship term",
    )
    interests: list[str] = Field(
        default_factory=lambda: [
            "Web3",
            "Software engineering",
            "Media / content",
            "Tech + culture intersection",
        ],
    )


DEFAULT_USER_PROFILE = UserProfile()
