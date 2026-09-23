// Purpose: normalize frontend generation and apply submissions into the
// canonical backend workflow command contract.
import { error, type Cookies } from '@sveltejs/kit';
import { createHash } from 'node:crypto';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

export type SmartDeckGenerationSubmission = {
  deckId: string;
  scope?: 'selected_slides' | 'current_slide' | 'selected_element';
  selectedSourceSlideIds: string[];
  activeSourceSlideId: string | null;
  instruction: string;
  deckType: string;
  audience: string | null;
  preferredModel: string | null;
  selectedElementId: string | null;
  selectedSubject: string | null;
  detectedSubjects: Array<Record<string, unknown>>;
  actionId: string | null;
  actionPrompt: string | null;
  userPrompt: string;
  latestBatchId: string | null;
  designContext: Record<string, unknown>;
  provenance: Record<string, unknown> | null;
  idempotencyKey: string;
  generationMode: 'standard' | 'instant_deck';
  outputContract: 'render_schema.v1' | 'full_html_deck.v1';
  baseDesignVersionId: string | null;
};

export type ApplyDesignVersionSubmission = {
  designVersionId: string;
  idempotencyKey: string;
};

function selectedIdsForScope(payload: {
  scope?: 'selected_slides' | 'current_slide' | 'selected_element';
  selectedSourceSlideIds?: string[];
  selectedSlideIds?: string[];
  activeSourceSlideId?: string | null;
  currentSlideId?: string | null;
}) {
  const currentSlideId = payload.currentSlideId ?? payload.activeSourceSlideId ?? null;
  if (payload.scope === 'current_slide') return currentSlideId ? [currentSlideId] : [];
  return payload.selectedSourceSlideIds ?? payload.selectedSlideIds ?? [];
}

// Accept both legacy shell fields and the current Smart Deck workspace payload.
export async function readSmartDeckGenerationSubmission(request: Request, fallbackDeckId?: string): Promise<SmartDeckGenerationSubmission> {
  const payload = (await request.json().catch(() => null)) as {
    deckId?: string;
    scope?: 'selected_slides' | 'current_slide' | 'selected_element';
    selectedSourceSlideIds?: string[];
    selectedSlideIds?: string[];
    activeSourceSlideId?: string | null;
    currentSlideId?: string | null;
    selectedElementId?: string | null;
    prompt?: string;
    instruction?: string;
    intentType?: 'redesign_slides';
    outputMode?: 'editable_slide_versions';
    deckType?: string;
    audience?: string | null;
    preferredModel?: string | null;
    selectedSubject?: string | null;
    detectedSubjects?: Array<Record<string, unknown>>;
    actionId?: string | null;
    actionPrompt?: string | null;
    userPrompt?: string | null;
    latestBatchId?: string | null;
    designContext?: Record<string, unknown>;
    provenance?: Record<string, unknown> | null;
    idempotencyKey?: string;
    generationMode?: 'standard' | 'instant_deck';
    outputContract?: 'render_schema.v1' | 'full_html_deck.v1';
    baseDesignVersionId?: string | null;
  } | null;

  const deckId = payload?.deckId || fallbackDeckId;
  if (!deckId) {
    throw error(400, 'deckId is required.');
  }
  const instruction = payload?.instruction?.trim() || payload?.prompt?.trim() || payload?.userPrompt?.trim() || '';
  if (!instruction) {
    throw error(400, 'instruction is required.');
  }
  if (payload?.intentType && payload.intentType !== 'redesign_slides') {
    throw error(400, 'intentType must be redesign_slides.');
  }
  if (payload?.outputMode && payload.outputMode !== 'editable_slide_versions') {
    throw error(400, 'outputMode must be editable_slide_versions.');
  }

  const selectedSourceSlideIds = selectedIdsForScope(payload ?? {});
  if (selectedSourceSlideIds.length === 0) {
    throw error(400, 'Select one or more slides to redesign.');
  }

  const idempotencySeed = JSON.stringify({
    deckId,
    selectedSourceSlideIds,
    activeSourceSlideId: payload?.activeSourceSlideId ?? payload?.currentSlideId ?? selectedSourceSlideIds[0] ?? null,
    instruction,
    deckType: payload?.deckType ?? 'unknown',
    audience: payload?.audience ?? null,
    preferredModel: payload?.preferredModel ?? null,
    selectedSubject: payload?.selectedSubject ?? null,
    actionId: payload?.actionId ?? null,
    actionPrompt: payload?.actionPrompt ?? null,
    userPrompt: payload?.userPrompt ?? instruction,
    latestBatchId: payload?.latestBatchId ?? null,
    provenance: payload?.provenance && typeof payload.provenance === 'object' ? payload.provenance : null,
    generationMode: payload?.generationMode === 'instant_deck' ? 'instant_deck' : 'standard',
    outputContract: payload?.outputContract === 'full_html_deck.v1' ? 'full_html_deck.v1' : 'render_schema.v1',
    baseDesignVersionId: payload?.baseDesignVersionId ?? null
  });

  return {
    deckId,
    scope: payload?.scope ?? 'selected_slides',
    selectedSourceSlideIds,
    activeSourceSlideId: payload?.activeSourceSlideId ?? payload?.currentSlideId ?? selectedSourceSlideIds[0] ?? null,
    instruction,
    deckType: payload?.deckType ?? 'unknown',
    audience: payload?.audience ?? null,
    preferredModel: payload?.preferredModel ?? null,
    selectedElementId: payload?.selectedElementId ?? null,
    selectedSubject: payload?.selectedSubject ?? null,
    detectedSubjects: payload?.detectedSubjects ?? [],
    actionId: payload?.actionId ?? null,
    actionPrompt: payload?.actionPrompt ?? null,
    userPrompt: payload?.userPrompt ?? instruction,
    latestBatchId: payload?.latestBatchId ?? null,
    designContext: payload?.designContext && typeof payload.designContext === 'object'
      ? payload.designContext
      : {
          mode: 'default_presentation',
          requiredFallbackOrder: ['brand_profile', 'logo', 'company_url', 'presentation', 'default_presentation'],
          mustNotBlockGeneration: true
        },
    provenance: payload?.provenance && typeof payload.provenance === 'object' ? payload.provenance : null,
    idempotencyKey: payload?.idempotencyKey?.trim().slice(0, 255) || `workflow:${deckId}:${createHash('sha256').update(idempotencySeed).digest('hex')}`,
    generationMode: payload?.generationMode === 'instant_deck' ? 'instant_deck' : 'standard',
    outputContract: payload?.outputContract === 'full_html_deck.v1' ? 'full_html_deck.v1' : 'render_schema.v1',
    baseDesignVersionId: payload?.baseDesignVersionId ?? null
  };
}

export async function readApplyDesignVersionSubmission(request: Request): Promise<ApplyDesignVersionSubmission> {
  const payload = (await request.json().catch(() => null)) as { designVersionId?: string; versionId?: string } | null;
  const designVersionId = payload?.designVersionId ?? payload?.versionId;

  if (!designVersionId) {
    throw error(400, 'designVersionId is required.');
  }

  return {
    designVersionId,
    idempotencyKey: `apply:${designVersionId}`
  };
}

export async function submitWorkflowCommand<TResponse>(
  fetcher: typeof fetch,
  cookies: Cookies,
  path: string,
  fallbackMessage: string,
  init: RequestInit = {}
): Promise<TResponse> {
  const backendUrl = requireBackendUrl();
  const headers = new Headers(init.headers);
  for (const [key, value] of Object.entries(requireBackendAuthHeaders(cookies))) {
    headers.set(key, String(value));
  }

  const response = await fetcher(`${backendUrl}${path}`, {
    ...init,
    headers
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(payload, fallbackMessage));
  }
  return payload as TResponse;
}
