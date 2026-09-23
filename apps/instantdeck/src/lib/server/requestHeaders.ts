import type { Cookies } from '@sveltejs/kit';
import { randomUUID } from 'node:crypto';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export function backendAuthHeaders(cookies: Cookies, requestId?: string | null): Headers {
  const headers = new Headers(requireBackendAuthHeaders(cookies));
  if (requestId?.trim()) {
    headers.set('x-request-id', requestId.trim());
  }
  if (!headers.has('x-request-id')) {
    headers.set('x-request-id', `fe-${randomUUID()}`);
  }
  return headers;
}
