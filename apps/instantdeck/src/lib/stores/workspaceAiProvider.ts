// Purpose: cache the workspace AI provider summary for product UI surfaces,
// while keeping failures retryable instead of silently freezing a null state.
import { writable } from 'svelte/store';
import type { WorkspaceAiProviderRouteResponse } from '@deck-aistack-codes/shared';
import { deckServiceClient } from '$lib/api/deckServiceClient';

export const workspaceAiProviderStore = writable<WorkspaceAiProviderRouteResponse['summary'] | null>(null);

let workspaceAiProviderLoadPromise: Promise<WorkspaceAiProviderRouteResponse['summary'] | null> | null = null;
let workspaceAiProviderLoaded = false;
let loadedWorkspaceId: string | null = null;

export function setWorkspaceAiProviderSummary(
  summary: WorkspaceAiProviderRouteResponse['summary'] | null,
  workspaceId: string | null = loadedWorkspaceId
) {
  workspaceAiProviderLoaded = true;
  loadedWorkspaceId = workspaceId;
  workspaceAiProviderStore.set(summary);
}

export function resetWorkspaceAiProviderSummary() {
  workspaceAiProviderLoaded = false;
  loadedWorkspaceId = null;
  workspaceAiProviderLoadPromise = null;
  workspaceAiProviderStore.set(null);
}

export async function loadWorkspaceAiProviderSummary(workspaceId: string | null = null) {
  if (workspaceAiProviderLoaded && loadedWorkspaceId === workspaceId) {
    return new Promise<WorkspaceAiProviderRouteResponse['summary'] | null>((resolve) => {
      workspaceAiProviderStore.subscribe((value) => resolve(value))();
    });
  }

  if (!workspaceAiProviderLoadPromise || loadedWorkspaceId !== workspaceId) {
    loadedWorkspaceId = workspaceId;
    const request = deckServiceClient.getWorkspaceAiProvider(workspaceId)
      .then((payload) => {
        if (loadedWorkspaceId !== workspaceId) return payload.summary;
        workspaceAiProviderLoaded = true;
        workspaceAiProviderStore.set(payload.summary);
        return payload.summary;
      })
      .catch((error) => {
        if (loadedWorkspaceId === workspaceId) workspaceAiProviderStore.set(null);
        throw error;
      })
      .finally(() => {
        if (workspaceAiProviderLoadPromise === request) workspaceAiProviderLoadPromise = null;
      });
    workspaceAiProviderLoadPromise = request;
  }

  return workspaceAiProviderLoadPromise;
}
