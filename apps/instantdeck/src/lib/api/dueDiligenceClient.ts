/**
 * Client for the Due Diligence chat endpoint.
 *
 * The backend exposes POST /api/products/deck-aistack-codes/decks/{deckId}/due-diligence/chat
 * which accepts a conversation history and returns an assistant reply grounded
 * in the deck's diligence workspace context.
 */

import { deckProductApiPath } from '$lib/contracts';

export interface DiligenceChatMessage {
  id?: string;
  conversationId?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  audience?: string | null;
  createdAt?: string;
}

export interface DiligenceChatRequest {
  messages: DiligenceChatMessage[];
  audience?: string | null;
  conversationId?: string | null;
  clientExchangeKey: string;
}

export interface DiligenceChatResponse {
  reply: string;
  provider?: string | null;
  model?: string | null;
  conversationId: string;
  messageId: string;
  clientExchangeKey: string;
  replayed: boolean;
}

export type AudienceDiligenceAction = 'analyze' | 'plan' | 'generate-smart-deck-instructions';

export interface AudienceDiligenceRequest {
  selectedAudience: string;
  conversionGoal?: string | null;
  userInstruction?: string | null;
  preferredModel?: string | null;
}

export interface AudienceDiligenceResponse {
  artifactId?: string | null;
  deckId: string;
  status: string;
  selectedAudience: string;
  audiencePriorities: string[];
  audienceObjections: Array<Record<string, unknown>>;
  audienceDecisionCriteria: string[];
  currentDeckFit: string;
  currentDeckFitScore: number;
  currentDeckFitReason: string;
  financialInsights: Record<string, unknown>;
  narrativeShift: string;
  deckImplementationPlan: Record<string, unknown>;
  slideLevelInstructions: Array<Record<string, unknown>>;
  missingEvidence: unknown[];
  smartDeckInstruction: Record<string, unknown>;
  smartEditInstructions: Array<Record<string, unknown>>;
  requiresReview: boolean;
}

async function readDiligenceError(response: Response, fallback: string): Promise<Error> {
  const payload = await response.json().catch(() => null);
  const detail =
    typeof payload?.error?.message === 'string'
      ? payload.error.message
      : typeof payload?.message === 'string'
        ? payload.message
        : typeof payload?.detail === 'string'
          ? payload.detail
          : typeof payload?.detail?.message === 'string'
            ? payload.detail.message
            : fallback;
  return new Error(detail);
}

export async function runAudienceDiligence(
  deckId: string,
  action: AudienceDiligenceAction,
  request: AudienceDiligenceRequest,
): Promise<AudienceDiligenceResponse> {
  const response = await fetch(deckProductApiPath(`/decks/${deckId}/due-diligence/audience/${action}`), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw await readDiligenceError(response, 'Audience diligence request failed.');
  return response.json() as Promise<AudienceDiligenceResponse>;
}

export async function getLatestAudienceDiligence(deckId: string): Promise<AudienceDiligenceResponse | null> {
  const response = await fetch(deckProductApiPath(`/decks/${deckId}/due-diligence/audience/latest`));
  if (response.status === 404) return null;
  if (!response.ok) throw await readDiligenceError(response, 'Latest audience diligence result could not be loaded.');
  return response.json() as Promise<AudienceDiligenceResponse>;
}

/**
 * Send a diligence chat message and receive an assistant reply.
 *
 * @param deckId     - The deck identifier.
 * @param messages   - Conversation history (most recent last). The backend
 *                     caps the context window to the last 20 messages.
 * @param audience   - Optional audience override sent with every request so
 *                     the LLM response is audience-contextualised.
 * @returns The assistant reply along with provider/model metadata.
 */
export async function sendDiligenceChatMessage(
  deckId: string,
  messages: DiligenceChatMessage[],
  audience?: string | null,
  conversationId?: string | null,
  clientExchangeKey: string = crypto.randomUUID(),
): Promise<DiligenceChatResponse> {
  const url = deckProductApiPath(`/decks/${deckId}/due-diligence/chat`);

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ messages, audience, conversationId, clientExchangeKey } satisfies DiligenceChatRequest),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      typeof payload?.error?.message === 'string'
        ? payload.error.message
        : typeof payload?.message === 'string'
          ? payload.message
          : typeof payload?.detail === 'string'
        ? payload.detail
        : typeof payload?.detail?.message === 'string'
          ? payload.detail.message
          : 'Diligence chat request failed.';
    throw new Error(detail);
  }

  return response.json() as Promise<DiligenceChatResponse>;
}
