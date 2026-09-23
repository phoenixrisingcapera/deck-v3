export type SmartDeckDeckType = 'startup_pitch' | 'vc_fund_pitch' | 'unknown';

export type SmartDeckSubject =
  | 'problem'
  | 'solution'
  | 'market_size'
  | 'traction'
  | 'business_model'
  | 'competition'
  | 'positioning'
  | 'why_now'
  | 'roadmap'
  | 'ask'
  | 'use_of_proceeds'
  | 'core_team'
  | 'extended_team'
  | 'product_walkthrough'
  | 'lighthouse_customers'
  | 'regulatory_tailwinds'
  | 'media_mentions'
  | 'references'
  | 'thought_leadership'
  | 'who_is_in'
  | 'blue_ocean_strategy'
  | 'fund_thesis'
  | 'portfolio_construction'
  | 'track_record'
  | 'pipeline'
  | 'lp_terms'
  | 'recent_exits'
  | 'unknown';

export interface SmartDeckSubjectDefinition {
  id: SmartDeckSubject;
  defaultSlug: string;
  slugVariants: string[];
  label: string;
  description: string;
  deckTypes: SmartDeckDeckType[];
  oftenBeforeSlides: SmartDeckSubject[];
  oftenAfterSlides: SmartDeckSubject[];
  requiredChecks: string[];
  investorLogic: string;
}

export interface SmartDeckSubjectPromptAction {
  id: string;
  subject: SmartDeckSubject;
  label: string;
  description: string;
  deckTypes: SmartDeckDeckType[];
  prompt: string;
  requiredChecks: string[];
}

export interface SmartDeckSubjectDetection {
  subject: SmartDeckSubject;
  confidence: number;
  matchedTerms: string[];
}

export interface SmartDeckGenerationTopicRequest {
  prompt: string;
  selectedSourceSlideIds: string[];
  activeSourceSlideId?: string | null;
  selectedElementId?: string | null;
  deckType?: SmartDeckDeckType;
  audience?: string | null;
  preferredModel?: string | null;
  selectedSubject?: SmartDeckSubject | null;
  detectedSubjects?: SmartDeckSubjectDetection[];
  actionId?: string | null;
  actionPrompt?: string | null;
  userPrompt?: string | null;
  latestBatchId?: string | null;
}
