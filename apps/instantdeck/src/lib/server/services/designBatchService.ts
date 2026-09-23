import type { Cookies } from '@sveltejs/kit';
import type { IterationDetail, IterationPreview } from '@deck-aistack-codes/shared';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';

function requireCookies(cookies: Cookies | undefined): Cookies {
  if (!cookies) {
    throw new Error('Authenticated backend access requires request cookies.');
  }
  return cookies;
}

function normalizeBatchPreview(payload: Record<string, unknown>): IterationPreview {
  return {
    id: String(payload.id ?? ''),
    deckId: String(payload.deckId ?? ''),
    iterationNumber: Number(payload.iterationNumber ?? payload.batchNumber ?? 0),
    batchNumber: Number(payload.batchNumber ?? payload.iterationNumber ?? 0),
    iterationName: payload.iterationName ? String(payload.iterationName) : payload.batchName ? String(payload.batchName) : null,
    batchName: payload.batchName ? String(payload.batchName) : payload.iterationName ? String(payload.iterationName) : null,
    scopeType: String(payload.scopeType ?? 'selected_slides') as IterationPreview['scopeType'],
    selectedSlideCount: Number(payload.selectedSlideCount ?? 0),
    status: String(payload.status ?? 'completed') as IterationPreview['status'],
    createdAt: String(payload.createdAt ?? new Date().toISOString())
  };
}

function normalizeBatchDetail(payload: Record<string, unknown>): IterationDetail {
  return {
    ...normalizeBatchPreview(payload),
    prompt: String(payload.prompt ?? ''),
    audienceLabel: payload.audienceLabel ? String(payload.audienceLabel) : null,
    selectedSlideIds: ((payload.selectedSlideIds ?? []) as unknown[]).map((item) => String(item)),
    candidateSlides: ((payload.candidateSlides ?? []) as Record<string, unknown>[]).map((candidate) => ({
      id: String(candidate.id ?? ''),
      iterationId: String(candidate.iterationId ?? candidate.batchId ?? ''),
      batchId: String(candidate.batchId ?? candidate.iterationId ?? ''),
      sourceSlideId: candidate.sourceSlideId ? String(candidate.sourceSlideId) : null,
      slideIndex: Number(candidate.slideIndex ?? 0),
      title: String(candidate.title ?? 'Untitled slide'),
      headline: String(candidate.headline ?? ''),
      summary: String(candidate.summary ?? ''),
      status: String(candidate.status ?? 'reviewable') as IterationDetail['candidateSlides'][number]['status']
    }))
  };
}

export async function listLatestDesignBatches(deckId: string, limit = 3, cookies?: Cookies): Promise<IterationPreview[]> {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/versions?limit=${limit}`)}`, {
    headers: requireBackendAuthHeaders(requireCookies(cookies))
  });
  if (!response.ok) {
    throw new Error('Could not load persisted design versions from the backend.');
  }

  const payload = (await response.json()) as { iterations?: Record<string, unknown>[]; batches?: Record<string, unknown>[] };
  return (payload.iterations ?? payload.batches ?? []).map(normalizeBatchPreview);
}

export async function getDesignBatchById(deckId: string, batchId: string, cookies?: Cookies): Promise<IterationDetail | undefined> {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/versions/${batchId}`)}`, {
    headers: requireBackendAuthHeaders(requireCookies(cookies))
  });
  if (!response.ok) {
    if (response.status === 404) {
      return undefined;
    }

    throw new Error('Could not load the requested design version.');
  }

  const payload = (await response.json()) as { iteration?: Record<string, unknown>; batch?: Record<string, unknown> };
  return payload.iteration ? normalizeBatchDetail(payload.iteration) : payload.batch ? normalizeBatchDetail(payload.batch) : undefined;
}
