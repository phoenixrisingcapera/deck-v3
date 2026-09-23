import type { SaveConfirmation } from '@deck-aistack-codes/shared';
import type { SaveConfirmationBannerModel } from '$lib/contracts/types';

export function normalizeSaveConfirmation(
  payload: Record<string, unknown> | null | undefined,
  fallbackEventType: SaveConfirmation['eventType'] = 'deck_upload_saved'
): SaveConfirmation | null {
  if (!payload) return null;

  return {
    id: String(payload.id ?? ''),
    deckId: String(payload.deckId ?? payload.deck_id ?? ''),
    workspaceId:
      typeof payload.workspaceId === 'string'
        ? payload.workspaceId
        : typeof payload.workspace_id === 'string'
          ? payload.workspace_id
          : null,
    userId:
      typeof payload.userId === 'string'
        ? payload.userId
        : typeof payload.user_id === 'string'
          ? payload.user_id
          : null,
    eventType: String(payload.eventType ?? payload.event_type ?? fallbackEventType) as SaveConfirmation['eventType'],
    entityType: String(payload.entityType ?? payload.entity_type ?? 'deck'),
    entityId:
      typeof payload.entityId === 'string'
        ? payload.entityId
        : typeof payload.entity_id === 'string'
          ? payload.entity_id
          : null,
    tone: String(payload.tone ?? 'success') as SaveConfirmation['tone'],
    title: String(payload.title ?? ''),
    message: String(payload.message ?? ''),
    ctaLabel:
      typeof payload.ctaLabel === 'string'
        ? payload.ctaLabel
        : typeof payload.cta_label === 'string'
          ? payload.cta_label
          : null,
    ctaHref:
      typeof payload.ctaHref === 'string'
        ? payload.ctaHref
        : typeof payload.cta_href === 'string'
          ? payload.cta_href
          : null,
    sourceSurface:
      typeof payload.sourceSurface === 'string'
        ? payload.sourceSurface
        : typeof payload.source_surface === 'string'
          ? payload.source_surface
          : null,
    sourceRoute:
      typeof payload.sourceRoute === 'string'
        ? payload.sourceRoute
        : typeof payload.source_route === 'string'
          ? payload.source_route
          : null,
    createdAt: String(payload.createdAt ?? payload.created_at ?? new Date().toISOString()),
    metadata: payload.metadata && typeof payload.metadata === 'object' ? (payload.metadata as Record<string, unknown>) : null
  };
}

export function toSaveConfirmationBannerModel(
  confirmation: SaveConfirmation | null | undefined,
  fallback?: SaveConfirmationBannerModel | null
): SaveConfirmationBannerModel | null {
  if (!confirmation) {
    return fallback ?? null;
  }

  return {
    title: confirmation.title,
    message: confirmation.message,
    tone: confirmation.tone,
    actionLabel: confirmation.ctaLabel,
    actionHref: confirmation.ctaHref
  };
}
