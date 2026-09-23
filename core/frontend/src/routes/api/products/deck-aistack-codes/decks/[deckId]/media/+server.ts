import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { extractErrorMessage, parseJson, proxyBackendJson, requireBackendUrl } from '$server/backendApi';
import { requireBackendAuthHeaders } from '$server/backendAuth';

export async function GET({ params, fetch, cookies, url }) {
  const query = url.searchParams.toString();
  return proxyBackendJson(fetch, cookies, `${deckProductApiPath(`/decks/${params.deckId}/media`)}${query ? `?${query}` : ''}`, {}, 'Media library could not be loaded.');
}

export async function POST({ params, request, fetch, cookies }) {
  const form = await request.formData();
  const file = form.get('file');
  const role = form.get('role');
  if (!(file instanceof File) || typeof role !== 'string') {
    return json({ error: { code: 'media_upload_invalid', message: 'A media file and role are required.' } }, { status: 400 });
  }
  const backendForm = new FormData();
  backendForm.set('file', file);
  backendForm.set('role', role);
  const label = form.get('label');
  if (typeof label === 'string' && label.trim()) backendForm.set('label', label.trim());
  const backendUrl = requireBackendUrl();
  const response = await fetch(`${backendUrl}${deckProductApiPath(`/decks/${params.deckId}/media`)}`, {
    method: 'POST', headers: requireBackendAuthHeaders(cookies), body: backendForm
  }).catch(() => null);
  if (!response) return json({ error: { code: 'media_upload_unavailable', message: 'Media upload could not reach the backend.' } }, { status: 503 });
  const payload = await parseJson(response);
  return json(response.ok ? payload : { error: { code: `http_${response.status}`, message: extractErrorMessage(payload, 'Media upload failed.') } }, { status: response.status });
}
