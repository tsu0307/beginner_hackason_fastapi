from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


StabilityLevel = Literal["high", "medium", "low"]
ChallengeLevel = Literal["high", "medium", "low"]
EventType = Literal["instant_event", "progression_event"]


class BranchCandidate(BaseModel):
    event: str = Field(min_length=1)
    stability: StabilityLevel = "medium"
    challenge: ChallengeLevel = "medium"
    event_type: EventType
    duration_years: int = Field(ge=0)

    @field_validator("event")
    @classmethod
    def validate_event(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("event must not be empty")
        return cleaned

    @field_validator("stability", "challenge", mode="before")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        mapping = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "\u9ad8": "high",
            "\u4e2d": "medium",
            "\u4f4e": "low",
        }
        return mapping.get(normalized, normalized)

    @model_validator(mode="after")
    def validate_event_type_duration(self) -> "BranchCandidate":
        if self.event_type == "instant_event" and self.duration_years != 0:
            raise ValueError("instant_event must use duration_years=0")
        if self.event_type == "progression_event" and self.duration_years < 1:
            raise ValueError("progression_event must use duration_years>=1")
        return self


class BranchResponse(BaseModel):
    branches: list[BranchCandidate] = Field(min_length=1)
