export type ProcessingStepStatus = 'done' | 'active' | 'pending' | 'failed';

export type ProcessingStep = {
  id: string;
  label: string;
  detail: string;
  status: ProcessingStepStatus;
};

export type UserProcessingStatus = {
  deckId: string;
  status: 'processing' | 'ready' | 'failed' | string;
  stage?: string;
  progress?: number;
  errorMessage?: string | null;
  readyForSmartDeck?: boolean;
};
