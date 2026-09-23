from pydantic import BaseModel, Field


class DeckMapCompanyBasics(BaseModel):
    companyName: str | None = None
    companyWebsiteUrl: str | None = None
    companyStage: str | None = None
    audience: str | None = None
    purpose: str | None = None
    summary: str | None = None


class DeckMapSlideDistribution(BaseModel):
    role: str
    count: int


class DeckMapSlideOverview(BaseModel):
    totalSlides: int
    byRole: list[DeckMapSlideDistribution]


class DeckMapClassificationSummary(BaseModel):
    semanticTag: str
    count: int
    sampleSlides: list[str] = Field(default_factory=list)


class DeckMapFindingsSummary(BaseModel):
    severity: str
    category: str
    count: int


class DeckMapResponse(BaseModel):
    deckId: str
    company: DeckMapCompanyBasics
    slideOverview: DeckMapSlideOverview
    classifications: list[DeckMapClassificationSummary]
    findings: list[DeckMapFindingsSummary]
