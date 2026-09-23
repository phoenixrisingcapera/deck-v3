import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';
import { backendAuthHeaders } from '$server/requestHeaders';

const MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024;

export async function POST({ request, fetch, cookies }) {
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath('/decks/upload-session')}`, {
    method: 'POST',
    headers: backendAuthHeaders(cookies, request.headers.get('x-request-id'))
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    return json(
      { message: extractErrorMessage(payload, 'Could not create upload session.') },
      { status: response.status }
    );
  }
  return json(payload ?? { acceptedFileTypes: ['pdf', 'ppt', 'pptx'], maxFileSizeBytes: MAX_FILE_SIZE_BYTES }, { status: response.status });
}
