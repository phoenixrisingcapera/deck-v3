export interface LatestGeneratedDeckCardModel {
  deckId: string;
  compiledDeckId?: string | null;
  title: string;
  status: 'ready' | 'under_review' | 'failed';
  sourceFileName?: string | null;
  latestBatchId: string;
  createdAt: string;
  finalizedAt: string;
  slideCount?: number;
  openHref: string;
  batchHref?: string;
}

interface CompiledDeckSlideModel {
  sourceSlideId?: string | null;
  generatedSlideCandidateId?: string | null;
  slideIndex: number;
  choice: 'generated_version' | 'original' | string;
  title: string;
  manifest: Record<string, unknown>;
}

export interface CompiledDeckModel {
  deckId: string;
  batchId: string;
  compiledDeckId: string;
  status: 'ready' | 'preparing' | 'failed' | string;
  title: string;
  slideCount: number;
  finalizedAt: string;
  manifest: Record<string, unknown>;
  slides: CompiledDeckSlideModel[];
}
