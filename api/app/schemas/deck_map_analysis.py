from pydantic import BaseModel, Field


class DeckMapCompany(BaseModel):
    name: str | None = None
    stage: str | None = None
    industry: str | None = None
    businessModel: str | None = None
    foundingTeam: str | None = None
    headquarters: str | None = None


class DeckMapSlideAnalysis(BaseModel):
    slideId: str
    title: str
    role: str
    purposeAssessment: str
    narrativeContribution: str
    strength: str
    improvementSuggestion: str | None = None


class DeckMapNarrative(BaseModel):
    arcType: str
    flowAssessment: str
    strengthAreas: list[str]
    weakAreas: list[str]
    recommendedRestructuring: str | None = None


class DeckMapEvidence(BaseModel):
    overallStrength: str
    quantitativeClaims: int = 0
    qualitativeClaims: int = 0
    dataSourcesCited: int = 0
    strongAreas: list[str]
    weakAreas: list[str]


class DeckMapGap(BaseModel):
    area: str
    importance: str
    suggestion: str


class DeckMapQualityScore(BaseModel):
    overall: int = Field(ge=1, le=100)
    narrativeFlow: int = Field(ge=1, le=100)
    evidenceQuality: int = Field(ge=1, le=100)
    investorReadiness: int = Field(ge=1, le=100)
    visualStructure: int = Field(ge=1, le=100)


class DeckMapAnalysisResponse(BaseModel):
    deckId: str
    company: DeckMapCompany
    narrative: DeckMapNarrative
    slides: list[DeckMapSlideAnalysis]
    evidence: DeckMapEvidence
    gaps: list[DeckMapGap]
    qualityScore: DeckMapQualityScore
    system: dict = Field(default_factory=dict)


class DeckMapAnalysisRunResponse(BaseModel):
    runId: str
    deckId: str
    status: str
    analysis: DeckMapAnalysisResponse | None = None
    cached: bool = False
