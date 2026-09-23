import type { Cookies } from '@sveltejs/kit';
import { getBackendAccessToken } from '$server/backendAuth';
import { requireBackendUrl } from '$server/backendApi';

export type FailureTicketReport = {
  route?: string | null;
  pageUrl?: string | null;
  apiPath?: string | null;
  statusCode?: number | null;
  userId?: string | null;
  userEmail?: string | null;
  deckId?: string | null;
  errorName?: string | null;
  errorMessage?: string | null;
  errorStack?: string | null;
  context?: Record<string, unknown>;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  source?: 'frontend' | 'api' | 'backend' | 'loader' | 'fallback';
  requestId?: string | null;
};

export async function reportFailureTicketToBackend(
  fetcher: typeof fetch,
  cookies: Cookies,
  report: FailureTicketReport
) {
  let backendUrl = '';
  try {
    backendUrl = requireBackendUrl();
  } catch {
    return null;
  }

  const headers = new Headers({ 'content-type': 'application/json' });
  const token = getBackendAccessToken(cookies);
  if (token) {
    headers.set('authorization', `Bearer ${token}`);
  }

  try {
    const response = await fetcher(`${backendUrl}/api/support/failure-tickets/report`, {
      method: 'POST',
      headers,
      body: JSON.stringify(report)
    });
    return response.ok ? response.json().catch(() => null) : null;
  } catch {
    return null;
  }
}
