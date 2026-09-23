import type { Cookies } from '@sveltejs/kit';
import type {
  DeckWorkspaceModel,
  GeneratedSlide,
  GeneratedSlideVersion,
  SaveConfirmation,
  SlideFeedbackEvent,
  SubmitSlideFeedbackRequest
} from '@deck-aistack-codes/shared';
import { deckProductApiPath } from '$lib/contracts';
import { normalizeSaveConfirmation } from '$lib/utils/saveConfirmation';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';

function normalizeGeneratedSlide(payload: Record<string, unknown>): GeneratedSlide {
  const layout = (payload.layout ?? {}) as Record<string, unknown>;

  return {
    id: String(payload.id ?? ''),
    slideType: String(payload.slide_type ?? payload.slideType ?? 'generic') as GeneratedSlide['slideType'],
    status: String(payload.status ?? 'needs_review') as GeneratedSlide['status'],
    title: String(payload.title ?? 'Untitled generated slide'),
    layout: {
      canvas: '16:9',
      composition: String(layout.composition ?? 'simple_text') as GeneratedSlide['layout']['composition'],
      safeMarginPx: Number(layout.safe_margin_px ?? layout.safeMarginPx ?? 48)
    },
    blocks: ((payload.blocks ?? []) as Record<string, unknown>[]).map((block) => ({
      id: String(block.id ?? ''),
      type: String(block.type ?? 'body') as GeneratedSlide['blocks'][number]['type'],
      text: String(block.text ?? ''),
      role: String(block.role ?? 'supporting') as GeneratedSlide['blocks'][number]['role'],
      x: Number(block.x ?? 0),
      y: Number(block.y ?? 0),
      w: Number(block.w ?? 10),
      h: Number(block.h ?? 10)
    })),
    speakerNotes: String(payload.speaker_notes ?? payload.speakerNotes ?? ''),
    designRationale: String(payload.design_rationale ?? payload.designRationale ?? ''),
    qualityFlags: ((payload.quality_flags ?? payload.qualityFlags ?? []) as unknown[]).map((item) => String(item)) as GeneratedSlide['qualityFlags']
  };
}

function normalizeWorkspaceSlide(payload: Record<string, unknown>): DeckWorkspaceModel['slides'][number] {
  return {
    id: String(payload.id ?? ''),
    deckId: String(payload.deckId ?? ''),
    slideNumber: Number(payload.slideNumber ?? 0),
    title: String(payload.title ?? 'Untitled slide'),
    rawText: String(payload.rawText ?? ''),
    summary: payload.summary ? String(payload.summary) : null,
    slideRole: String(payload.slideRole ?? 'unknown') as DeckWorkspaceModel['slides'][number]['slideRole'],
    blocks: ((payload.blocks ?? []) as Record<string, unknown>[]).map((block) => ({
      id: String(block.id ?? ''),
      deckId: block.deckId ? String(block.deckId) : undefined,
      slideId: String(block.slideId ?? ''),
      blockIndex: Number(block.blockIndex ?? 0),
      blockType: String(block.blockType ?? 'body') as DeckWorkspaceModel['slides'][number]['blocks'][number]['blockType'],
      rawText: String(block.rawText ?? ''),
      currentText: String(block.currentText ?? block.rawText ?? ''),
      normalizedText: block.normalizedText ? String(block.normalizedText) : null,
      classification: block.classification
        ? {
            id: String((block.classification as Record<string, unknown>).id ?? ''),
            blockId: String((block.classification as Record<string, unknown>).blockId ?? ''),
            semanticTag: String((block.classification as Record<string, unknown>).semanticTag ?? ''),
            diligenceCategory: String((block.classification as Record<string, unknown>).diligenceCategory ?? ''),
            confidence: Number((block.classification as Record<string, unknown>).confidence ?? 0)
          }
        : null
    }))
  };
}

function normalizeVersion(payload: Record<string, unknown>): GeneratedSlideVersion {
  return {
    id: String(payload.id ?? ''),
    generationRunId: String(payload.generationRunId ?? ''),
    sourceSlideId: payload.sourceSlideId ? String(payload.sourceSlideId) : null,
    slideIndex: Number(payload.slideIndex ?? 0),
    sourceSlideTitle: payload.sourceSlideTitle ? String(payload.sourceSlideTitle) : null,
    versionNumber: Number(payload.versionNumber ?? 1),
    title: String(payload.title ?? 'Generated version'),
    status: String(payload.status ?? 'reviewable') as GeneratedSlideVersion['status'],
    generatedSlide: normalizeGeneratedSlide((payload.generatedSlide ?? {}) as Record<string, unknown>),
    createdAt: String(payload.createdAt ?? new Date().toISOString()),
    updatedAt: String(payload.updatedAt ?? new Date().toISOString())
  };
}

function normalizeFeedback(payload: Record<string, unknown>): SlideFeedbackEvent {
  return {
    id: String(payload.id ?? ''),
    slideVersionId: String(payload.slideVersionId ?? ''),
    generationRunId: payload.generationRunId ? String(payload.generationRunId) : null,
    sourceSlideId: payload.sourceSlideId ? String(payload.sourceSlideId) : null,
    eventType: String(payload.eventType ?? 'viewed') as SlideFeedbackEvent['eventType'],
    notes: payload.notes ? String(payload.notes) : null,
    payload: (payload.payload ?? null) as Record<string, unknown> | null,
    createdAt: String(payload.createdAt ?? new Date().toISOString())
  };
}

function normalizeWorkspace(payload: Record<string, unknown>): DeckWorkspaceModel {
  const deck = (payload.deck ?? {}) as Record<string, unknown>;

  return {
    deck: {
      id: String(deck.id ?? ''),
      workspaceId: String(deck.workspaceId ?? ''),
      title: String(deck.title ?? 'Uploaded deck'),
      audience: String(deck.audience ?? 'Investment Committee'),
      purpose: String(deck.purpose ?? 'Initial diligence review'),
      status: String(deck.status ?? 'ready') as DeckWorkspaceModel['deck']['status'],
      summary: String(deck.summary ?? ''),
      createdAt: String(deck.createdAt ?? new Date().toISOString()),
      updatedAt: String(deck.updatedAt ?? new Date().toISOString()),
      generationStatus: String(deck.generationStatus ?? 'idle') as DeckWorkspaceModel['deck']['generationStatus'],
      generationMode: String(deck.generationMode ?? 'openai') as DeckWorkspaceModel['deck']['generationMode'],
      latestGenerationRunId: deck.latestGenerationRunId ? String(deck.latestGenerationRunId) : null
    },
    slides: ((payload.slides ?? []) as Record<string, unknown>[]).map(normalizeWorkspaceSlide),
    versions: ((payload.versions ?? []) as Record<string, unknown>[]).map(normalizeVersion),
    feedback: ((payload.feedback ?? []) as Record<string, unknown>[]).map(normalizeFeedback)
  };
}

export async function getDeckWorkspaceModel(
  deckId: string,
  cookies?: Cookies
): Promise<{ workspace: DeckWorkspaceModel; latestConfirmation: SaveConfirmation | null } | undefined> {
  const backendUrl = requireBackendUrl();

  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/workspace`)}`, {
    headers: cookies ? requireBackendAuthHeaders(cookies) : undefined
  });
  if (!response.ok) {
    if (response.status === 404) {
      return undefined;
    }

    throw new Error('Could not load the Deck AIStack workspace model from the backend.');
  }

  const payload = (await response.json()) as {
    workspace?: Record<string, unknown>;
    latestConfirmation?: Record<string, unknown> | null;
  };

  return payload.workspace
    ? {
        workspace: normalizeWorkspace(payload.workspace),
        latestConfirmation: normalizeSaveConfirmation(payload.latestConfirmation, 'deck_properties_saved')
      }
    : undefined;
}

export async function submitWorkspaceSlideFeedback(
  deckId: string,
  slideId: string,
  input: SubmitSlideFeedbackRequest,
  cookies: Cookies
): Promise<{ feedback: SlideFeedbackEvent; workspace: DeckWorkspaceModel }> {
  const backendUrl = requireBackendUrl();

  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/slides/${slideId}/feedback`)}`, {
    method: 'POST',
    headers: {
      ...requireBackendAuthHeaders(cookies),
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(input)
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const payload = (await response.json()) as {
    feedback?: Record<string, unknown>;
    workspace?: Record<string, unknown>;
  };

  if (!payload.feedback || !payload.workspace) {
    throw new Error('The backend did not return the updated feedback workspace payload.');
  }

  return {
    feedback: normalizeFeedback(payload.feedback),
    workspace: normalizeWorkspace(payload.workspace)
  };
}
