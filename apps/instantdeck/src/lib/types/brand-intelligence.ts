export type BrandIntelligencePhase =
  | 'waiting'
  | 'reading_deck'
  | 'sampling_url'
  | 'reading_logo'
  | 'brand_ready'
  | 'needs_user_input'
  | 'failed';

export interface BrandIntelligenceSwatch {
  label: string;
  value: string;
  source: 'deck' | 'url' | 'logo' | 'fallback' | 'manual';
  confidence: number;
}

export interface BrandIntelligenceState {
  deckId: string;
  phase: BrandIntelligencePhase;
  smartSwatches: BrandIntelligenceSwatch[];
  optionalInputs: {
    companyUrl?: string;
    linkedinUrls?: string[];
    teamImageFiles?: File[];
    logoFile?: File;
    brandGuidelinesFile?: File;
  };
}
