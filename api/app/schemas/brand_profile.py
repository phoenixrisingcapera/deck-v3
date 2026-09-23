from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BrandLogoPayload(BaseModel):
    assetId: str | None = None
    url: str | None = None
    mimeType: str | None = None
    fileName: str | None = None


class BrandColorsPayload(BaseModel):
    primary: str
    secondary: str | None = None
    accent: str | None = None
    background: str | None = None
    surface: str | None = None
    text: str | None = None
    mutedText: str | None = None
    palette: list[str] = Field(default_factory=list)


class BrandUsageRulesPayload(BaseModel):
    preferredBackground: str = "auto"
    useLogoColorsFirst: bool = True
    avoidLowContrast: bool = True
    keepInvestorGrade: bool = True
    preserveSourceDeckStructure: bool = True


class BrandDesignHintsPayload(BaseModel):
    mood: list[str] = Field(default_factory=list)
    visualStyle: str | None = None
    deckUseCase: str | None = None


class BrandingJsonPayload(BaseModel):
    brandProfileId: str
    company: dict[str, str | None]
    logo: BrandLogoPayload
    colors: BrandColorsPayload
    usageRules: BrandUsageRulesPayload
    designHints: BrandDesignHintsPayload
    llmInstructions: list[str] = Field(default_factory=list)


def normalize_branding_json_payload(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    try:
        return BrandingJsonPayload.model_validate(value).model_dump()
    except ValueError:
        return None


class BrandPaletteSwatchPayload(BaseModel):
    label: str
    value: str


class BrandSourceLabelPayload(BaseModel):
    key: str
    label: str
    status: str = "pending"
    detail: str | None = None


class BrandFieldEvidencePayload(BaseModel):
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["extracted", "fallback", "overridden"]


class DeckBrandProfilePayload(BaseModel):
    id: str
    deckId: str
    status: str = "idle"
    companyName: str | None = None
    companyWebsiteUrl: str | None = None
    logoUrl: str | None = None
    faviconUrl: str | None = None
    brandSummary: str | None = None
    visualDirection: str | None = None
    visualStyle: str | None = None
    audienceLabel: str | None = None
    primaryGoal: str | None = None
    primaryColor: str | None = None
    secondaryColor: str | None = None
    accentColor: str | None = None
    backgroundColor: str | None = None
    textColor: str | None = None
    palette: list[str] = Field(default_factory=list)
    deterministicSwatches: list[BrandPaletteSwatchPayload] = Field(default_factory=list)
    deterministicMappingVersion: str | None = None
    fontCandidates: list[str] = Field(default_factory=list)
    fieldEvidence: dict[str, BrandFieldEvidencePayload] = Field(default_factory=dict)
    sourceLabels: list[BrandSourceLabelPayload] = Field(default_factory=list)
    confidenceScore: float | None = None
    sourceMode: str | None = None
    warnings: list[str] = Field(default_factory=list)
    rawEvidence: dict = Field(default_factory=dict)
    brandingJson: BrandingJsonPayload | None = None
    brandGuidelinesFileUrl: str | None = None
    brandGuidelinesStatus: str | None = None
    processingStatus: str = "ready"
    updatedAt: str | None = None


class BrandExtractionStagePayload(BaseModel):
    key: str
    label: str
    status: str
    progressPercent: int


class BrandExtractionStatusResponse(BaseModel):
    deckId: str
    status: str
    progressPercent: int
    brandProfileId: str | None = None
    sourceMode: str | None = None
    stages: list[BrandExtractionStagePayload] = Field(default_factory=list)
    assets: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    brandProfile: DeckBrandProfilePayload | None = None


class DeckBrandProfileRouteResponse(BaseModel):
    deckId: str
    brandProfile: DeckBrandProfilePayload


class ExtractDeckBrandRouteResponse(BaseModel):
    brandProfileId: str
    status: str = "completed"
    brandProfile: DeckBrandProfilePayload


class UpdateDeckBrandProfileRequest(BaseModel):
    companyName: str | None = None
    companyWebsiteUrl: str | None = None
    logoUrl: str | None = None
    faviconUrl: str | None = None
    brandSummary: str | None = None
    visualDirection: str | None = None
    visualStyle: str | None = None
    audienceLabel: str | None = None
    primaryGoal: str | None = None
    primaryColor: str | None = None
    secondaryColor: str | None = None
    accentColor: str | None = None
    backgroundColor: str | None = None
    textColor: str | None = None
    palette: list[str] | None = None
    fontCandidates: list[str] | None = None
    sourceLabels: list[BrandSourceLabelPayload] | None = None
    confidenceScore: float | None = None
    sourceMode: str | None = None
    warnings: list[str] | None = None
