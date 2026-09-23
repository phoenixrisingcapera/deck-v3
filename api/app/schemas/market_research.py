from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class MarketResearchSource(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    url: str
    provider: str | None = Field(default=None, max_length=120)
    publishedDate: date | None = None

    @field_validator("url")
    @classmethod
    def validate_safe_url(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("source URL contains control characters")
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("source URL must be an absolute HTTP(S) URL without credentials")
        return value


class MarketResearchCompany(BaseModel):
    name: str | None = None
    description: str | None = None
    foundedYear: int | None = None
    headquarters: str | None = None
    businessModel: str | None = None
    fundingStage: str | None = None
    totalRaised: str | None = None
    teamSize: str | None = None
    keyFinding: str | None = None


class MarketResearchSizing(BaseModel):
    tam: str | None = None
    sam: str | None = None
    som: str | None = None
    growthRate: str | None = None
    sourceConfidence: str
    note: str | None = None
    citationIds: list[str] = Field(default_factory=list)


class MarketResearchCompetitor(BaseModel):
    name: str
    category: str
    threats: str | None = None
    weaknesses: str | None = None
    differentiation: str | None = None
    citationIds: list[str] = Field(default_factory=list)


class MarketResearchThesis(BaseModel):
    summary: str
    strengths: list[str]
    weaknesses: list[str]
    differentiators: list[str]
    citationIds: list[str] = Field(default_factory=list)


class MarketResearchRisk(BaseModel):
    risk: str
    severity: str
    mitigation: str | None = None
    citationIds: list[str] = Field(default_factory=list)


class MarketResearchVcAssessment(BaseModel):
    score: int = Field(ge=1, le=100)
    stageFit: str
    strengths: list[str]
    concerns: list[str]
    diligenceQuestions: list[str] = Field(default_factory=list)
    citationIds: list[str] = Field(default_factory=list)


class MarketResearchResponse(BaseModel):
    deckId: str
    company: MarketResearchCompany
    marketSizing: MarketResearchSizing
    competitors: list[MarketResearchCompetitor]
    industryTrends: str | None = None
    investmentThesis: MarketResearchThesis
    risks: list[MarketResearchRisk]
    vcAssessment: MarketResearchVcAssessment
    system: dict = Field(default_factory=dict)
    sources: list[MarketResearchSource] = Field(default_factory=list)
    citationStatus: Literal["cited", "partial", "uncited", "no_sources"] = "no_sources"


class MarketResearchRunResponse(BaseModel):
    runId: str
    deckId: str
    status: str
    research: MarketResearchResponse | None = None
    cached: bool = False
