export type BrandSourceMode = 'logo_upload' | 'manual_url' | 'manual' | 'logo_and_url';

export type BrandConfidenceLabel = 'Low confidence' | 'Medium confidence' | 'High confidence';

export interface BrandPaletteSwatch {
  label: string;
  value: string;
}

export interface DeckServiceBrandingJson {
  brandProfileId: string;
  company: {
    name?: string;
    websiteUrl?: string;
  };
  logo: {
    assetId?: string;
    url?: string;
    mimeType?: string;
    fileName?: string;
  };
  colors: {
    primary: string;
    secondary?: string;
    accent?: string;
    background?: string;
    surface?: string;
    text?: string;
    mutedText?: string;
    palette: string[];
  };
  usageRules: {
    preferredBackground: 'dark' | 'light' | 'auto';
    useLogoColorsFirst: boolean;
    avoidLowContrast: boolean;
    keepInvestorGrade: boolean;
    preserveSourceDeckStructure: boolean;
  };
  designHints: {
    mood: string[];
    visualStyle: string;
    deckUseCase: string;
  };
  llmInstructions: string[];
}

export interface DeckServiceBrandProfile {
  id: string;
  sourceMode: BrandSourceMode;
  companyUrl?: string;
  logoUrl?: string;
  logoFileName?: string;
  logoMimeType?: string;
  summary: string;
  primaryColor: string;
  secondaryColor: string;
  accentColor: string;
  backgroundColor: string;
  textColor: string;
  surfaceColor: string;
  mutedTextColor: string;
  palette: BrandPaletteSwatch[];
  fontCandidates: string[];
  visualStyle: string;
  confidenceScore: number;
  confidenceLabel: BrandConfidenceLabel;
  source: {
    fromWebsite: boolean;
    fromDeck: boolean;
    fromLogo: boolean;
    fromCss: boolean;
    fromScreenshot: boolean;
  };
  brandingJson: DeckServiceBrandingJson;
}
