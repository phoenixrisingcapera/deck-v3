import type { DeckGraph } from '$types/domain';

export type SmartDeckDesignContext = {
  mode: 'brand_profile' | 'presentation_derived' | 'default_presentation';
  requiredFallbackOrder: ['brand_profile', 'logo', 'company_url', 'presentation', 'default_presentation'];
  mustNotBlockGeneration: true;
  source: {
    hasBrandProfile: boolean;
    hasLogo: boolean;
    hasCompanyUrl: boolean;
    hasPresentation: boolean;
  };
  instructions: string[];
  defaultTokens: {
    background: string;
    surface: string;
    text: string;
    muted: string;
    accent: string;
  };
};

function hasPresentationSignals(graph: DeckGraph | null | undefined) {
  return Boolean(graph?.slides?.length || graph?.deck?.title || graph?.deck?.purpose || graph?.deck?.audience);
}

export function buildSmartDeckDesignContext(options: {
  graph?: DeckGraph | null;
  hasBrandProfile?: boolean;
  hasLogo?: boolean;
  hasCompanyUrl?: boolean;
} = {}): SmartDeckDesignContext {
  const hasPresentation = hasPresentationSignals(options.graph);
  const hasBrandProfile = Boolean(options.hasBrandProfile);
  const hasLogo = Boolean(options.hasLogo);
  const hasCompanyUrl = Boolean(options.hasCompanyUrl);
  const mode = hasBrandProfile
    ? 'brand_profile'
    : hasPresentation
      ? 'presentation_derived'
      : 'default_presentation';

  return {
    mode,
    requiredFallbackOrder: ['brand_profile', 'logo', 'company_url', 'presentation', 'default_presentation'],
    mustNotBlockGeneration: true,
    source: { hasBrandProfile, hasLogo, hasCompanyUrl, hasPresentation },
    instructions: [
      'Never block Smart Deck generation because brand extraction is missing, failed, skipped, or still running.',
      'If a verified brand profile exists, use it.',
      'If brand is missing, infer color, typography, spacing, and tone from the uploaded presentation itself.',
      'If logo or company URL signals are available, use them as optional enhancement only.',
      'If no usable brand or presentation styling exists, use the default professional presentation tokens.'
    ],
    defaultTokens: {
      background: '#020617',
      surface: '#0f172a',
      text: '#f8fafc',
      muted: '#94a3b8',
      accent: '#0ea5e9'
    }
  };
}
