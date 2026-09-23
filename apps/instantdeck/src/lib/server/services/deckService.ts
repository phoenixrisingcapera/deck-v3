import type { Cookies } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';
import type { Deck, DeckExport, DeckGraph } from '$types/domain';

function normalizeBackendDeck(payload: Record<string, unknown>): Deck {
  const filePayload = (payload.file ?? null) as Record<string, unknown> | null;

  return {
    id: String(payload.id ?? ''),
    workspaceId: String(payload.workspace_id ?? payload.workspaceId ?? 'ws_backend'),
    title: String(payload.title ?? 'Uploaded deck'),
    audience: String(payload.audience ?? 'Investment Committee'),
    purpose: String(payload.purpose ?? 'Initial diligence review'),
    status: String(payload.status ?? 'uploaded') as Deck['status'],
    summary: String(payload.summary ?? payload.description ?? ''),
    createdAt: String(payload.created_at ?? payload.createdAt ?? new Date().toISOString()),
    updatedAt: String(payload.updated_at ?? payload.updatedAt ?? new Date().toISOString()),
    thumbnailUrl:
      typeof payload.thumbnailUrl === 'string'
        ? payload.thumbnailUrl
        : typeof payload.thumbnail_url === 'string'
          ? payload.thumbnail_url
          : null,
    previewUrl:
      typeof payload.previewUrl === 'string'
        ? payload.previewUrl
        : typeof payload.preview_url === 'string'
          ? payload.preview_url
          : null,
    firstSlideId:
      typeof payload.firstSlideId === 'string'
        ? payload.firstSlideId
        : typeof payload.first_slide_id === 'string'
          ? payload.first_slide_id
          : null,
    originalFilename:
      typeof payload.originalFilename === 'string'
        ? payload.originalFilename
        : typeof payload.original_filename === 'string'
          ? payload.original_filename
          : undefined,
    file: filePayload
      ? {
          id: String(filePayload.id ?? ''),
          filename: String(filePayload.original_filename ?? filePayload.originalFilename ?? filePayload.filename ?? 'uploaded-deck'),
          mimeType: String(filePayload.mime_type ?? filePayload.mimeType ?? 'application/octet-stream'),
          size: Number(filePayload.size ?? 0),
          uploadedAt: String(filePayload.uploaded_at ?? filePayload.uploadedAt ?? payload.updated_at ?? payload.updatedAt ?? new Date().toISOString())
        }
      : undefined
  };
}

function normalizeBackendGraph(payload: Record<string, unknown>): DeckGraph {
  const deckPayload = (payload.deck ?? {}) as Record<string, unknown>;
  const filePayload = deckPayload.file as Record<string, unknown> | undefined;
  const llmArtifacts = ((payload.llmArtifacts ?? payload.llm_artifacts ?? []) as Record<string, unknown>[])
    .filter((artifact) => artifact && typeof artifact === 'object');

  return {
    deck: {
      id: String(deckPayload.id ?? ''),
      workspaceId: String(deckPayload.workspaceId ?? deckPayload.workspace_id ?? 'ws_backend'),
      title: String(deckPayload.title ?? 'Uploaded deck'),
      audience: String(deckPayload.audience ?? 'Investment Committee'),
      purpose: String(deckPayload.purpose ?? 'Initial diligence review'),
      status: String(deckPayload.status ?? 'uploaded') as Deck['status'],
      summary: String(deckPayload.summary ?? ''),
      createdAt: String(deckPayload.createdAt ?? deckPayload.created_at ?? new Date().toISOString()),
      updatedAt: String(deckPayload.updatedAt ?? deckPayload.updated_at ?? new Date().toISOString()),
      file: filePayload
        ? {
            id: String(filePayload.id ?? ''),
            filename: String(filePayload.filename ?? filePayload.original_filename ?? 'uploaded-deck.pdf'),
            mimeType: String(filePayload.mimeType ?? filePayload.mime_type ?? 'application/pdf'),
            size: Number(filePayload.size ?? 0),
            uploadedAt: String(filePayload.uploadedAt ?? filePayload.uploaded_at ?? new Date().toISOString())
          }
        : undefined
    },
    slides: ((payload.slides ?? []) as Record<string, unknown>[]).map((slide) => ({
      id: String(slide.id ?? ''),
      deckId: String(slide.deckId ?? slide.deck_id ?? ''),
      slideIndex: Number(slide.slideIndex ?? slide.slide_index ?? 0),
      slideNumber: Number(slide.slideNumber ?? slide.slide_number ?? slide.slideIndex ?? slide.slide_index ?? 0),
      title: String(slide.title ?? 'Untitled slide'),
      role: String(slide.role ?? 'unknown'),
      rawText: String(slide.rawText ?? slide.raw_text ?? ''),
      extractedText: String(slide.extractedText ?? slide.extracted_text ?? slide.rawText ?? slide.raw_text ?? ''),
      narrativeNotes: String(slide.narrativeNotes ?? slide.narrative_notes ?? ''),
      summary: typeof slide.summary === 'string' ? slide.summary : null,
      status: String(slide.status ?? 'ready'),
      previewUrl:
        typeof slide.previewUrl === 'string'
          ? slide.previewUrl
          : typeof slide.preview_url === 'string'
            ? slide.preview_url
            : null,
      previewImageUrl:
        typeof slide.previewImageUrl === 'string'
          ? slide.previewImageUrl
          : typeof slide.preview_image_url === 'string'
            ? slide.preview_image_url
            : null,
      thumbnailUrl:
        typeof slide.thumbnailUrl === 'string'
          ? slide.thumbnailUrl
          : typeof slide.thumbnail_url === 'string'
            ? slide.thumbnail_url
            : null,
      previewWidth:
        typeof slide.previewWidth === 'number'
          ? slide.previewWidth
          : typeof slide.preview_width === 'number'
            ? slide.preview_width
            : null,
      previewHeight:
        typeof slide.previewHeight === 'number'
          ? slide.previewHeight
          : typeof slide.preview_height === 'number'
            ? slide.preview_height
            : null,
      previewMimeType:
        typeof slide.previewMimeType === 'string'
          ? slide.previewMimeType
          : typeof slide.preview_mime_type === 'string'
            ? slide.preview_mime_type
            : null
    })),
    blocks: ((payload.blocks ?? []) as Record<string, unknown>[]).map((block) => ({
      id: String(block.id ?? ''),
      slideId: String(block.slideId ?? block.slide_id ?? ''),
      blockIndex: Number(block.blockIndex ?? block.block_index ?? 0),
      rawText: String(block.rawText ?? block.raw_text ?? ''),
      normalizedText: String(block.normalizedText ?? block.normalized_text ?? ''),
      blockType: String(block.blockType ?? block.block_type ?? 'body') as DeckGraph['blocks'][number]['blockType'],
      position: block.position ? String(block.position) : undefined,
      style: block.style ? String(block.style) : undefined
    })),
    classifications: ((payload.classifications ?? []) as Record<string, unknown>[]).map((item) => ({
      id: String(item.id ?? ''),
      blockId: String(item.blockId ?? item.block_id ?? ''),
      semanticTag: String(item.semanticTag ?? item.semantic_tag ?? 'unknown'),
      diligenceCategory: String(item.diligenceCategory ?? item.diligence_category ?? 'unknown'),
      confidence: Number(item.confidence ?? 0)
    })),
    findings: ((payload.findings ?? []) as Record<string, unknown>[]).map((item) => ({
      id: String(item.id ?? ''),
      deckId: String(item.deckId ?? item.deck_id ?? ''),
      slideId: String(item.slideId ?? item.slide_id ?? ''),
      blockId: item.blockId || item.block_id ? String(item.blockId ?? item.block_id) : undefined,
      title: String(item.title ?? ''),
      detail: String(item.detail ?? ''),
      severity: String(item.severity ?? 'low') as DeckGraph['findings'][number]['severity'],
      category: String(item.category ?? 'unknown')
    })),
    suggestions: ((payload.suggestions ?? []) as Record<string, unknown>[]).map((item) => ({
      id: String(item.id ?? ''),
      deckId: String(item.deckId ?? item.deck_id ?? ''),
      slideId: String(item.slideId ?? item.slide_id ?? ''),
      blockId: item.blockId || item.block_id ? String(item.blockId ?? item.block_id) : undefined,
      title: String(item.title ?? ''),
      reason: String(item.reason ?? ''),
      suggestedText: String(item.suggestedText ?? item.suggested_text ?? ''),
      status: String(item.status ?? 'pending') as DeckGraph['suggestions'][number]['status'],
      audience: String(item.audience ?? 'Investment Committee')
    })),
    smartEditSuggestions: ((payload.smartEditSuggestions ?? payload.smart_edit_suggestions ?? []) as Record<string, unknown>[]).map((item) => ({
      id: String(item.id ?? ''),
      runId: String(item.runId ?? item.run_id ?? ''),
      deckId: String(item.deckId ?? item.deck_id ?? ''),
      slideId: String(item.slideId ?? item.slide_id ?? ''),
      blockId: String(item.blockId ?? item.block_id ?? ''),
      originalText: String(item.originalText ?? item.original_text ?? ''),
      suggestedText: String(item.suggestedText ?? item.suggested_text ?? ''),
      reason: String(item.reason ?? ''),
      riskLevel: String(item.riskLevel ?? item.risk_level ?? 'low') as DeckGraph['smartEditSuggestions'][number]['riskLevel'],
      status: String(item.status ?? 'pending') as DeckGraph['smartEditSuggestions'][number]['status']
    })),
    revisions: ((payload.revisions ?? []) as Record<string, unknown>[]).map((item) => ({
      id: String(item.id ?? ''),
      deckId: String(item.deckId ?? item.deck_id ?? ''),
      slideId: String(item.slideId ?? item.slide_id ?? ''),
      blockId: String(item.blockId ?? item.block_id ?? ''),
      previousText: String(item.previousText ?? item.previous_text ?? ''),
      nextText: String(item.nextText ?? item.next_text ?? ''),
      reason: String(item.reason ?? ''),
      createdAt: String(item.createdAt ?? item.created_at ?? new Date().toISOString())
    })),
    // Preserve backend artifact history on the canonical deck graph so mounted
    // Smart Deck panels can load saved LLM analyses from product data.
    llmArtifacts,
    llm_artifacts: llmArtifacts
  };
}

function requireCookies(cookies: Cookies | undefined): Cookies {
  if (!cookies) {
    throw new Error('Authenticated backend access requires request cookies.');
  }
  return cookies;
}

export async function listDeckSummaries(options?: { enableInspectionFallback?: boolean; cookies?: Cookies }): Promise<Deck[]> {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath('/decks')}`, {
    headers: requireBackendAuthHeaders(requireCookies(options?.cookies))
  });
  if (!response.ok) throw new Error('Could not load persisted deck summaries from the backend.');
  const payload = (await response.json()) as { decks?: Record<string, unknown>[] };
  return (payload.decks ?? []).map(normalizeBackendDeck);
}

export async function loadDeckGraph(deckId: string, options?: { enableInspectionFallback?: boolean; cookies?: Cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/graph`)}`, {
    headers: requireBackendAuthHeaders(requireCookies(options?.cookies))
  });
  if (response.status === 404) return undefined;
  if (!response.ok) throw new Error('Could not load the persisted Smart Deck graph from the backend.');
  return normalizeBackendGraph((await response.json()) as Record<string, unknown>);
}
