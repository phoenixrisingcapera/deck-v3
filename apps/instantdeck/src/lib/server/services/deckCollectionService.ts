import { error, json, type Cookies } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage } from '$server/backendApi';
import { reportFailureTicketToBackend } from '$server/failureTickets';
import { normalizeWorkspaceDeckRecord } from '$server/services/workspaceDeckRecordsService';
import {
  SUPPORTED_BRAND_GUIDE_EXTENSIONS,
  SUPPORTED_BRAND_GUIDE_MIME_TYPES,
  SUPPORTED_LOGO_EXTENSIONS,
  SUPPORTED_LOGO_MIME_TYPES,
  firstFile,
  firstString,
  isSupportedDeckUpload,
  isSupportedUpload,
  normalizeUpload,
  normalizeUploadFailure,
  requireBackend,
  resolveRequestId,
  responseHeaders,
  stringList,
  textOrNull,
  uploadContext,
  withRequestId
} from '$server/services/deckUploadService';

export async function loadWorkspaceDecks(fetcher: typeof fetch, cookies: Cookies) {
  const backendUrl = requireBackend();
  let headers: HeadersInit;

  try {
    headers = requireBackendAuthHeaders(cookies);
  } catch {
    return json({ decks: [] }, { status: 200 });
  }

  const response = await fetcher(`${backendUrl}${deckProductApiPath('/decks')}`, { headers });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    await reportFailureTicketToBackend(fetcher, cookies, {
      apiPath: deckProductApiPath('/decks'),
      statusCode: response.status,
      errorName: 'WorkspaceDeckListResponseError',
      errorMessage: extractErrorMessage(payload, 'Could not load workspace decks.'),
      severity: response.status >= 500 ? 'high' : 'medium',
      source: 'api',
      requestId: response.headers.get('x-request-id'),
      context: { phase: 'deck_list' }
    });

    if (response.status < 500) {
      return json({ decks: [] }, { status: 200 });
    }

    throw error(response.status, extractErrorMessage(payload, 'Could not load workspace decks.'));
  }

  const decks = Array.isArray(payload?.decks)
    ? payload.decks.map((deck: unknown) => normalizeWorkspaceDeckRecord(deck as Record<string, unknown>))
    : [];
  return json({ decks }, { status: response.status });
}

export async function createWorkspaceDeck(request: Request, fetcher: typeof fetch, cookies: Cookies) {
  const backendUrl = requireBackend();
  const form = await request.formData();
  const file = form.get('file') ?? form.get('deck');
  const workspaceId = firstString(form, 'workspaceId', 'workspace_id');
  const companyName = firstString(form, 'companyName', 'company_name');
  const websiteUrl = firstString(form, 'websiteUrl', 'website_url');
  const audience = firstString(form, 'audience') || 'Investment Committee';
  const purpose = firstString(form, 'purpose') || 'Initial diligence review';
  const founderName = firstString(form, 'founderName', 'founder_name');
  const notes = firstString(form, 'notes');
  const teamNotes = firstString(form, 'teamNotes', 'team_notes');
  const linkedinUrls = stringList(form, 'linkedinUrls', 'linkedin_urls');
  const supportingUrls = stringList(form, 'supportingUrls', 'supporting_urls');
  const brandGuide = firstFile(form, 'brandGuide', 'brand_guide', 'brandGuidelinesFile');
  const logoFile = firstFile(form, 'logoFile', 'logo_file');

  if (!(file instanceof File)) {
    throw error(400, 'file is required');
  }

  if (!isSupportedDeckUpload(file)) {
    throw error(400, 'Only PDF, PPT, and PPTX uploads are supported.');
  }
  if (logoFile && !isSupportedUpload(logoFile, SUPPORTED_LOGO_EXTENSIONS, SUPPORTED_LOGO_MIME_TYPES)) {
    throw error(400, 'Only PNG, JPEG, GIF, and WebP logo uploads are supported.');
  }
  if (brandGuide && !isSupportedUpload(brandGuide, SUPPORTED_BRAND_GUIDE_EXTENSIONS, SUPPORTED_BRAND_GUIDE_MIME_TYPES)) {
    throw error(400, 'Only PDF, DOC, DOCX, TXT, and Markdown brand guidelines uploads are supported.');
  }

  const backendForm = new FormData();
  backendForm.set('deck', file);
  if (workspaceId) backendForm.set('workspace_id', workspaceId);
  if (companyName) backendForm.set('company_name', companyName);
  if (websiteUrl) backendForm.set('website_url', websiteUrl);
  backendForm.set('audience', audience);
  backendForm.set('purpose', purpose);
  if (founderName) backendForm.set('founder_name', founderName);
  if (notes) backendForm.set('notes', notes);
  if (teamNotes) backendForm.set('team_notes', teamNotes);
  if (linkedinUrls.length > 0) backendForm.set('linkedin_urls', linkedinUrls.join('\n'));
  if (supportingUrls.length > 0) backendForm.set('supporting_urls', supportingUrls.join('\n'));
  if (brandGuide) backendForm.set('brand_guide', brandGuide);
  if (logoFile) backendForm.set('logo_file', logoFile);

  const requestId = resolveRequestId(request, { ensureUploadRequestId: true });

  let response: Response;
  try {
    response = await fetcher(`${backendUrl}${deckProductApiPath('/decks/upload')}`, {
      method: 'POST',
      headers: withRequestId(request, requireBackendAuthHeaders(cookies), requestId),
      body: backendForm
    });
  } catch {
    const message = 'Frontend upload proxy could not reach the backend.';
    const detail = uploadContext(file, 'frontend_upload_proxy_fetch', {
      requestId
    });
    await reportFailureTicketToBackend(fetcher, cookies, {
      apiPath: deckProductApiPath('/decks/upload'),
      statusCode: 503,
      errorName: 'BackendFetchUnavailable',
      errorMessage: message,
      severity: 'critical',
      source: 'api',
      requestId,
      context: detail
    });

    return json(
      {
        ok: false,
        message: 'Deck upload service is temporarily unreachable. The upload outcome is unknown.',
        status: 503,
        requestId,
        failureCategory: 'frontend_upload_proxy_fetch',
        ticketId: null,
        recoverable: true
      },
      { status: 503, headers: responseHeaders(requestId) }
    );
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const backendRequestId =
      response.headers.get('x-request-id') ?? response.headers.get('x-railway-request-id') ?? requestId;
    const failure = normalizeUploadFailure(payload, response.status, 'Deck upload failed.', backendRequestId);
    const responseRequestId = textOrNull(failure.requestId) ?? textOrNull(backendRequestId);
    const failureCategory = String(failure.failureCategory ?? 'backend_upload_response_error');

    await reportFailureTicketToBackend(fetcher, cookies, {
      apiPath: deckProductApiPath('/decks/upload'),
      statusCode: response.status,
      errorName: String(failure.errorName ?? 'DeckUploadResponseError'),
      errorMessage: String(failure.message ?? 'Deck upload failed.'),
      severity: response.status >= 500 ? 'critical' : 'medium',
      source: 'api',
      requestId: responseRequestId,
      context: uploadContext(file, failureCategory, {
        backendTicketId: failure.ticketId ?? null,
        responseStatus: response.status
      })
    });

    return json(failure, { status: response.status, headers: responseHeaders(responseRequestId) });
  }

  const backendRequestId = response.headers.get('x-request-id') ?? response.headers.get('x-railway-request-id') ?? requestId;
  return json(normalizeUpload(payload as Record<string, unknown>), {
    status: response.status,
    headers: responseHeaders(backendRequestId)
  });
}
