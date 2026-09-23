export type AudienceType =
  | 'Investment Committee'
  | 'VC Partner'
  | 'VC Associate'
  | 'Strategic Investor'
  | 'Family Office'
  | 'LP'
  | 'Corporate Development'
  | 'M&A Buyer'
  | 'Board'
  | 'Accelerator';

export type DeckType = 'pitch_deck' | 'ic_deck' | 'lp_update' | 'board_deck' | 'ma_deck';
export type DeckFileType = 'ppt' | 'pptx' | 'pdf' | 'key' | 'other';
export type DiligenceStage = 'initial_review' | 'partner_review' | 'ic_review' | 'deep_diligence' | 'final_approval';
export type DeckStatus =
  | 'draft'
  | 'uploaded'
  | 'extracting'
  | 'extraction_failed'
  | 'parsing'
  | 'structuring'
  | 'extracting_blocks'
  | 'classifying_blocks'
  | 'analysing'
  | 'adapting'
  | 'reviewed'
  | 'ready'
  | 'failed';
export type ProcessingStepStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ExportType = 'diligence_report' | 'adapted_outline' | 'change_log' | 'annotated_deck' | 'pptx' | 'pdf';
export type BillingInterval = 'monthly' | 'annual';
export type WorkspaceSubscriptionStatus = 'trialing' | 'active' | 'past_due' | 'canceled';
export type BillingInvoiceStatus = 'draft' | 'open' | 'paid' | 'void';
export type ConnectedAccountProvider = 'microsoft' | 'linkedin';
export type ConnectedAccountStatus = 'connected' | 'needs_reauth' | 'disconnected' | 'syncing';
export type WorkspaceAiProvider = 'openai' | 'openrouter' | 'claude' | 'qwen';
export type DesignBatchScopeType = 'whole_deck' | 'selected_slides' | 'new_slides_only' | 'appendix';
export type DesignBatchStatus = 'running' | 'completed' | 'reviewed' | 'failed';
// Keep legacy provider labels in the type for compatibility with older payloads,
// but current production uses `openai` for generation semantics.
export type DeckServiceGenerationMode = 'mock' | 'claude' | 'openai' | 'openrouter' | 'dashscope' | 'qwen';
export type GeneratedDeckTheme = 'dark' | 'light' | 'auto';
export type GeneratedSlideVersionStatus = 'generated' | 'reviewable' | 'accepted' | 'rejected' | 'edited' | 'applied';
export type SlideFeedbackEventType = 'accepted' | 'rejected' | 'edited' | 'viewed';
export type DeckShellToolId = 'deck_map' | 'research' | 'slides' | 'design' | 'elements' | 'text' | 'media' | 'data' | 'ai_tools' | 'brand' | 'settings' | 'smart_edit' | 'due_diligence';

export interface DeckSummary {
  id: string;
  title: string;
  companyName?: string;
  audience: AudienceType;
  purpose: string;
  status: DeckStatus;
  summary: string;
  readinessScore?: number | null;
  openFindingsCount?: number;
  updatedAt?: string;
}

export interface FirstTimeTemplatePreview {
  id: string;
  title: string;
  audienceLabel: string;
  description: string;
  tags: string[];
  ctaLabel: string;
}

export interface WorkspaceSummary {
  workspace: { id: string; name: string };
  deckCount: number;
  activeDeckId: string | null;
  latestDecks: DeckSummary[];
  processingDeckCount: number;
  readyDeckCount: number;
  exportCount: number;
  firstTimeTemplates: FirstTimeTemplatePreview[];
}

export interface DeckProcessingStatus {
  deckId: string;
  status: DeckStatus;
  steps: Array<{
    key: 'upload' | 'parsing' | 'structuring' | 'extracting_blocks' | 'classifying_blocks' | 'analysing' | 'adapting' | 'workspace_ready';
    label: string;
    status: ProcessingStepStatus;
    errorMessage?: string | null;
  }>;
}

export interface SmartEditRequest {
  slideId: string;
  blockId: string;
  audienceType?: string;
  instruction: string;
}

export interface DeckSlideBlockContract {
  id: string;
  deckId?: string;
  slideId: string;
  blockIndex: number;
  blockType: 'title' | 'subtitle' | 'body' | 'bullet' | 'metric' | 'chart_label' | 'caption' | 'source_note' | 'footer' | 'speaker_note' | 'headline' | 'quote' | 'unknown';
  rawText: string;
  currentText: string;
  normalizedText: string | null;
  classification?: { id: string; blockId: string; semanticTag: string; diligenceCategory: string; confidence: number } | null;
}

export interface DeckSlideWithBlocks {
  id: string;
  deckId: string;
  slideNumber: number;
  title: string;
  rawText: string;
  summary: string | null;
  slideRole: 'cover' | 'problem' | 'solution' | 'market' | 'product' | 'traction' | 'business_model' | 'competition' | 'team' | 'financials' | 'ask' | 'appendix' | 'unknown';
  blocks: DeckSlideBlockContract[];
}

export interface ChangeReviewItem {
  id: string;
  sourceType: 'adaptation_suggestion' | 'smart_edit';
  deckId: string;
  slideId: string | null;
  blockId: string | null;
  slideNumber: number | null;
  slideTitle: string | null;
  originalText: string | null;
  suggestedText: string;
  finalText: string | null;
  reason: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'applied' | 'no_change';
}

export interface CreateExportRequest {
  exportType: ExportType;
  includeFindings: boolean;
  includeSuggestions: boolean;
  includeSmartEdits: boolean;
  includeRejected: boolean;
}

export interface SmartEditResponse {
  smartEditRunId: string;
  suggestion: {
    id: string;
    smartEditRunId: string;
    deckId: string;
    slideId: string;
    blockId: string;
    originalText: string;
    suggestedText: string;
    finalText: string | null;
    reason: string;
    riskLevel: 'low' | 'medium' | 'high' | 'critical';
    status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'applied' | 'no_change';
  };
}

export interface UpdateSmartEditSuggestionRequest {
  status: 'accepted' | 'rejected' | 'edited';
  finalText?: string;
}

export interface Deck {
  id: string;
  workspaceId: string;
  title: string;
  audience: string;
  purpose: string;
  status: DeckStatus;
  createdAt: string;
  updatedAt: string;
  summary: string;
  file?: { id: string; filename: string; mimeType: string; size: number; uploadedAt: string };
  thumbnailUrl?: string | null;
  previewUrl?: string | null;
  firstSlideId?: string | null;
  originalFilename?: string | null;
}

export interface DeckSlide {
  id: string;
  deckId: string;
  slideIndex: number;
  slideNumber?: number;
  title: string;
  role: string;
  rawText: string;
  extractedText?: string;
  summary?: string | null;
  narrativeNotes: string;
  status?: 'ready' | 'pending' | string;
  previewUrl?: string | null;
  previewImageUrl?: string | null;
  thumbnailUrl?: string | null;
  previewWidth?: number | null;
  previewHeight?: number | null;
  previewMimeType?: string | null;
}

export interface DeckSlideBlock {
  id: string;
  slideId: string;
  blockIndex: number;
  rawText: string;
  normalizedText: string;
  blockType: 'headline' | 'body' | 'metric' | 'quote' | 'bullet';
  position?: string;
  style?: string;
}

export interface BlockClassification {
  id: string;
  blockId: string;
  semanticTag: string;
  diligenceCategory: string;
  confidence: number;
}

export interface AnalysisFinding {
  id: string;
  deckId: string;
  slideId: string;
  blockId?: string;
  title: string;
  detail: string;
  severity: 'high' | 'medium' | 'low';
  category: string;
}

export interface AdaptationSuggestion {
  id: string;
  deckId: string;
  slideId: string;
  blockId?: string;
  title: string;
  reason: string;
  suggestedText: string;
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'applied' | 'no_change';
  audience: string;
}

export interface SmartEditRun {
  id: string;
  deckId: string;
  slideId: string;
  blockId: string;
  instruction: string;
  status?: 'queued' | 'generating' | 'completed' | 'failed';
  createdAt: string;
}

export interface SmartEditSuggestion {
  id: string;
  runId: string;
  deckId: string;
  slideId: string;
  blockId: string;
  originalText: string;
  suggestedText: string;
  reason: string;
  riskLevel: 'low' | 'medium' | 'high';
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'applied' | 'no_change';
}

export interface DeckSlideRevision {
  id: string;
  deckId: string;
  slideId: string;
  blockId: string;
  previousText: string;
  nextText: string;
  reason: string;
  createdAt: string;
}

export interface DeckExport {
  id: string;
  deckId: string;
  type: 'diligence_report' | 'adapted_outline' | 'final_deck' | string;
  content: string;
  createdAt: string;
  downloadUrl?: string;
  designVersionId?: string | null;
  format?: string | null;
  filename?: string | null;
  mediaType?: string | null;
}

export interface DeckExportShare {
  shareId: string;
  deckId: string;
  exportId: string;
  designVersionId: string;
  status: 'active' | 'revoked';
  createdAt: string;
  expiresAt?: string | null;
  revokedAt?: string | null;
  lastAccessedAt?: string | null;
  accessCount: number;
}

export interface DeckExportShareCreated extends DeckExportShare {
  shareToken: string;
  publicPath: string;
}

export interface DeckGraph {
  deck: Deck;
  slides: DeckSlide[];
  blocks: DeckSlideBlock[];
  classifications: BlockClassification[];
  findings: AnalysisFinding[];
  suggestions: AdaptationSuggestion[];
  smartEditSuggestions: SmartEditSuggestion[];
  revisions: DeckSlideRevision[];
  llmArtifacts?: Record<string, unknown>[];
  llm_artifacts?: Record<string, unknown>[];
}

export interface BillingPlan {
  id: string;
  code: string;
  name: string;
  description: string;
  monthlyPriceCents: number | null;
  annualPriceCents: number | null;
  ctaLabel: string;
  isHighlighted: boolean;
  isEnterprise: boolean;
  seatLabel: string | null;
  featureBullets: string[];
}

export interface BillingInvoice {
  id: string;
  invoiceNumber: string;
  status: BillingInvoiceStatus;
  amountCents: number;
  currency: string;
  issuedAt: string;
  paidAt: string | null;
}

export interface WorkspaceSubscription {
  id: string;
  workspaceId: string;
  billingPlanId: string;
  status: WorkspaceSubscriptionStatus;
  interval: BillingInterval;
  seatCount: number;
  cancelAtPeriodEnd: boolean;
  currentPeriodStart: string;
  currentPeriodEnd: string;
}

export interface BillingWorkspaceSnapshot {
  workspace: { id: string; name: string };
  plans: BillingPlan[];
  currentPlan: BillingPlan | null;
  subscription: WorkspaceSubscription | null;
  invoices: BillingInvoice[];
}

export interface UserConnectedAccount {
  id: string;
  provider: ConnectedAccountProvider;
  status: ConnectedAccountStatus;
  externalAccountId: string | null;
  externalEmail: string | null;
  externalDisplayName: string | null;
  externalProfileUrl: string | null;
  scopes: string[];
  accessTokenMasked: string | null;
  refreshTokenStored: boolean;
  lastSyncedAt: string | null;
  syncMetadataJson: Record<string, unknown> | null;
}

export interface UserProfileSnapshot {
  id: string;
  userId: string;
  displayName: string | null;
  headline: string | null;
  companyName: string | null;
  jobTitle: string | null;
  department: string | null;
  city: string | null;
  region: string | null;
  country: string | null;
  timezone: string | null;
  preferredLanguage: string | null;
  photoUrl: string | null;
  bio: string | null;
  linkedinProfileUrl: string | null;
  microsoftTenantId: string | null;
  workEmail: string | null;
  mobilePhone: string | null;
  skillsJson: unknown;
  educationJson: unknown;
  certificationsJson: unknown;
  profileSourceJson: Record<string, unknown> | null;
}

export interface UserSettingsSnapshot {
  user: { id: string; email: string; name: string };
  profile: UserProfileSnapshot | null;
  connectedAccounts: UserConnectedAccount[];
}

export interface ConnectUserAccountRequest {
  provider: ConnectedAccountProvider;
  origin?: 'settings_page' | 'connected_accounts_page' | 'reminder_popup';
}

export interface IterationPreview {
  id: string;
  deckId: string;
  iterationNumber: number;
  batchNumber?: number;
  iterationName: string | null;
  batchName?: string | null;
  scopeType: DesignBatchScopeType;
  selectedSlideCount: number;
  status: DesignBatchStatus;
  createdAt: string;
}

export type DesignBatchPreview = IterationPreview;

export interface DeckWorkspacePreferences {
  deckId: string;
  activeTool: DeckShellToolId;
  leftPanelOpen: boolean;
  selectedSlideId: string | null;
  lastBatchId: string | null;
  lastSlideVersionId: string | null;
  selectedElementType: string | null;
  selectedDataView: string | null;
  chatOpen: boolean;
  updatedAt: string | null;
}

export interface UpdateDeckWorkspacePreferencesRequest {
  activeTool?: DeckShellToolId;
  leftPanelOpen?: boolean;
  selectedSlideId?: string | null;
  lastBatchId?: string | null;
  lastSlideVersionId?: string | null;
  selectedElementType?: string | null;
  selectedDataView?: string | null;
  chatOpen?: boolean;
}

export interface UpdateDeckBlockRequest {
  text: string;
  normalizedText?: string | null;
  reason?: string | null;
}

export interface DeckShellProperties {
  deckId: string;
  companyName: string | null;
  companyWebsiteUrl: string | null;
  contactEmail: string | null;
  companyStage: string | null;
  founderName: string | null;
  teamSummary: string | null;
  brandSummary: string | null;
  visualDirection: string | null;
  audienceLabel: string | null;
  primaryGoal: string | null;
  processingStatus: 'draft' | 'ready' | 'needs_review';
  sourceFileName: string | null;
  brandReady: boolean;
  sourcesUsed: string[];
  brandAssetLabels: string[];
  updatedAt: string | null;
}

export interface UpdateDeckShellPropertiesRequest {
  companyName?: string | null;
  companyWebsiteUrl?: string | null;
  founderName?: string | null;
  teamSummary?: string | null;
  brandSummary?: string | null;
  visualDirection?: string | null;
  audienceLabel?: string | null;
  primaryGoal?: string | null;
}

export interface CreateDeckSlideRequest {
  title?: string;
  role?: string;
  rawText?: string;
}

export interface CreateDesignBatchRequest {
  scopeType: Extract<DesignBatchScopeType, 'whole_deck' | 'selected_slides'>;
  prompt: string;
  iterationName?: string | null;
  audienceLabel?: string | null;
  selectedSlideIds?: string[];
  useBrandProfile?: boolean;
  useWebsiteContext?: boolean;
  useBlockClassifications?: boolean;
}

export interface GeneratedSlideCandidate {
  id: string;
  iterationId: string;
  batchId?: string;
  sourceSlideId: string | null;
  slideIndex: number;
  title: string;
  headline: string;
  summary: string;
  status: 'generated' | 'reviewable' | 'applied' | 'kept_original';
}

export interface ReviewGeneratedSlideCandidateRequest {
  decision: 'keep_version' | 'keep_original';
}

export interface IterationDetail extends IterationPreview {
  prompt: string;
  audienceLabel: string | null;
  selectedSlideIds: string[];
  candidateSlides: GeneratedSlideCandidate[];
}

export type DesignBatchDetail = IterationDetail;

export interface GeneratedSlideBlock {
  id: string;
  type: 'heading' | 'subheading' | 'body' | 'metric' | 'caption' | 'quote' | 'image_placeholder' | 'shape' | 'button_label';
  text: string;
  role: 'primary' | 'secondary' | 'supporting' | 'decorative';
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface GeneratedSlideLayout {
  canvas: '16:9';
  composition: 'hero' | 'two_column' | 'three_cards' | 'timeline' | 'metric_grid' | 'quote' | 'image_left' | 'image_right' | 'simple_text';
  safeMarginPx: number;
}

export interface GeneratedSlide {
  id: string;
  slideType: 'cover' | 'problem' | 'solution' | 'market' | 'product' | 'traction' | 'business_model' | 'competition' | 'team' | 'financials' | 'roadmap' | 'ask' | 'generic';
  status: 'ok' | 'needs_review' | 'failed';
  title: string;
  layout: GeneratedSlideLayout;
  blocks: GeneratedSlideBlock[];
  speakerNotes: string;
  designRationale: string;
  qualityFlags: Array<'ok' | 'text_too_dense' | 'low_contrast_risk' | 'image_collision_risk' | 'needs_human_review'>;
}

export interface GeneratedSlideVersion {
  id: string;
  generationRunId: string;
  sourceSlideId: string | null;
  slideIndex: number;
  sourceSlideTitle: string | null;
  versionNumber: number;
  title: string;
  status: GeneratedSlideVersionStatus;
  generatedSlide: GeneratedSlide;
  createdAt: string;
  updatedAt: string;
}

export interface SlideFeedbackEvent {
  id: string;
  slideVersionId: string;
  generationRunId: string | null;
  sourceSlideId: string | null;
  eventType: SlideFeedbackEventType;
  notes: string | null;
  payload: Record<string, unknown> | null;
  createdAt: string;
}

export interface DeckWorkspaceModel {
  deck: Deck & {
    generationStatus: 'idle' | 'running' | 'ready' | 'failed';
    generationMode: DeckServiceGenerationMode;
    latestGenerationRunId: string | null;
  };
  slides: DeckSlideWithBlocks[];
  versions: GeneratedSlideVersion[];
  feedback: SlideFeedbackEvent[];
}

export interface SubmitSlideFeedbackRequest {
  slideVersionId: string;
  eventType: SlideFeedbackEventType;
  notes?: string | null;
  applyToWorkspace?: boolean;
}

export interface FirstDeckUploadResult {
  ok: true;
  deckId: string;
  filename: string;
  deckExtractionStatus?: 'idle' | 'queued' | 'processing' | 'ready' | 'failed';
  preferredWorkspace?: 'smart_deck' | 'instant_deck';
  preferredWorkspaceUrl?: string | null;
  queueError?: string | null;
  queueFailureTicketId?: string | null;
  requestId?: string | null;
  failureTicketId?: string | null;
  processing?: Record<string, unknown> | null;
  confirmation?: SaveConfirmation | null;
  workspace: WorkspaceSummary;
}

export type SaveConfirmationTone = 'success' | 'info' | 'warning' | 'danger';

export interface SaveConfirmationBannerModel {
  title: string;
  message?: string | null;
  tone?: SaveConfirmationTone;
  timestampLabel?: string | null;
  actionLabel?: string | null;
  actionHref?: string | null;
}

export type SaveConfirmationEventType =
  | 'deck_upload_saved'
  | 'deck_properties_saved'
  | 'deck_block_saved'
  | 'brand_profile_saved'
  | 'workspace_preferences_saved';

export interface SaveConfirmation {
  id: string;
  deckId: string;
  workspaceId: string | null;
  userId: string | null;
  eventType: SaveConfirmationEventType;
  entityType: string;
  entityId: string | null;
  tone: SaveConfirmationTone;
  title: string;
  message: string;
  ctaLabel: string | null;
  ctaHref: string | null;
  sourceSurface: string | null;
  sourceRoute: string | null;
  createdAt: string;
  metadata?: Record<string, unknown> | null;
}

export interface SaveWorkspaceAiProviderRequest {
  provider: WorkspaceAiProvider;
  workspaceId?: string | null;
  apiKey: string;
  preferredModel?: string | null;
  reasoningModel?: string | null;
  embeddingModel?: string | null;
  skipForNow?: boolean;
}

export interface WorkspaceAiModelDescriptor {
  id: string;
  label: string;
  category: 'chat' | 'reasoning' | 'embedding' | 'vision';
  supportsChat: boolean;
  supportsReasoning: boolean;
  supportsEmbeddings: boolean;
  supportsVision: boolean;
  enabled: boolean;
}

export interface WorkspaceAiProviderSummary {
  provider: WorkspaceAiProvider | null;
  preferredModel: string | null;
  reasoningModel: string | null;
  embeddingModel: string | null;
  apiKeyLast4: string | null;
  isConfigured: boolean;
  configuredAt: string | null;
  skippedAt: string | null;
  providerLabel: string | null;
  providerEnabled: boolean;
  discoverySupported: boolean;
  validationStatus: 'unconfigured' | 'validated' | 'skipped' | 'degraded';
  availableModels: WorkspaceAiModelDescriptor[];
  defaults: {
    chat?: string | null;
    reasoning?: string | null;
    embedding?: string | null;
    vision?: string | null;
  };
}
