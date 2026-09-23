import { error, json, redirect } from '@sveltejs/kit';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

function withRequestId(request: Request, headers: HeadersInit = {}) {
  const requestId = request.headers.get('x-request-id')?.trim();
  if (!requestId) {
    return headers;
  }

  return {
    ...headers,
    'x-request-id': requestId
  };
}

export async function GET({ fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}/api/decks`, {
    headers: requireBackendAuthHeaders(cookies)
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(payload, 'Could not load decks.'));
  }
  return json(payload, { status: response.status });
}

export async function POST({ request, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const contentType = request.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  let payload: Record<string, string>;

  if (isJson) {
    payload = await request.json();
  } else {
    const form = await request.formData();
    payload = Object.fromEntries(form.entries()) as Record<string, string>;
  }

  const response = await fetch(`${backendUrl}/api/decks`, {
    method: 'POST',
    headers: {
      ...withRequestId(request, requireBackendAuthHeaders(cookies)),
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      title: payload.title ?? 'Untitled deck',
      audience: payload.audience ?? 'Investment Committee',
      purpose: payload.purpose ?? 'Series A diligence memo prep',
      workspace_id: payload.workspaceId ?? payload.workspace_id,
      summary: payload.companyName
        ? `${payload.companyName} deck created for ${payload.audience ?? 'Investment Committee'} review.`
        : 'New upload queued for parsing.'
    })
  });
  const result = await response.json().catch(() => null);

  if (!response.ok) {
    throw error(response.status, extractErrorMessage(result, 'Could not create deck.'));
  }

  const deck = result?.deck ?? result;

  if (!deck?.id) {
    throw error(502, 'Backend did not return a deck id.');
  }

  const deckId = String(deck.id);

  /*
   * Legacy local sample creation was removed from this route. Empty deck creation
   * now belongs to FastAPI so the tester's workspace remains database-backed.
   */
  if (!isJson) {
    throw redirect(303, `/decks/${deckId}/smart-deck`);
  }

  return json({ deck }, { status: response.status });
}
