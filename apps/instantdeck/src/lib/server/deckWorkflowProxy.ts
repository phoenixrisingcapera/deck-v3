import { error, type Cookies } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';
import { deckWorkflowJobApiPath, deckWorkflowStateApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

export async function fetchBackendJsonOrThrow(
  fetcher: typeof fetch,
  cookies: Cookies,
  path: string,
  fallbackMessage: string,
  init: RequestInit = {}
) {
  const backendUrl = requireBackendUrl();
  const headers = new Headers(init.headers);
  for (const [key, value] of Object.entries(requireBackendAuthHeaders(cookies))) {
    headers.set(key, String(value));
  }
  if (!headers.has('x-request-id')) {
    headers.set('x-request-id', `fe-${randomUUID()}`);
  }

  const response = await fetcher(`${backendUrl}${path}`, {
    ...init,
    headers
  });
  const payload = await response.json().catch(() => null);
  const requestId = response.headers.get('x-request-id') ?? response.headers.get('x-railway-request-id') ?? headers.get('x-request-id');
  if (!response.ok) {
    const err = new Error(extractErrorMessage(payload, fallbackMessage)) as Error & {
      backendStatus?: number;
      backendStatusText?: string;
      backendPath?: string;
      backendPayload?: Record<string, unknown> | null;
      requestId?: string | null;
    };
    err.backendStatus = response.status;
    err.backendStatusText = response.statusText;
    err.backendPath = path;
    err.backendPayload = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
    err.requestId = requestId;
    throw error(response.status, Object.assign(err, {
      backendStatus: response.status,
      backendStatusText: response.statusText,
      backendPath: path,
      backendPayload: payload,
      requestId
    }));
  }
  return payload;
}

export async function fetchWorkflowState(fetcher: typeof fetch, cookies: Cookies, deckId: string) {
  return fetchBackendJsonOrThrow(
    fetcher,
    cookies,
    deckWorkflowStateApiPath(deckId),
    'Could not load deck workflow state.'
  );
}

export async function fetchWorkflowJob(fetcher: typeof fetch, cookies: Cookies, jobId: string) {
  return fetchBackendJsonOrThrow(
    fetcher,
    cookies,
    deckWorkflowJobApiPath(jobId),
    'Could not load workflow job status.'
  );
}
