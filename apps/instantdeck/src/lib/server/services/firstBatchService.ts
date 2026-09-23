import { json, type Cookies, error } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

const SUPPORTED_FIRST_BATCH_TYPES = new Set(['url_branding', 'logo_branding']);
const SUPPORTED_LOGO_EXTENSIONS = ['.gif', '.jpg', '.jpeg', '.png', '.webp'] as const;
const SUPPORTED_LOGO_MIME_TYPES = new Set(['image/gif', 'image/jpeg', 'image/png', 'image/webp']);

function firstString(form: FormData, ...keys: string[]) {
  for (const key of keys) {
    const value = form.get(key);
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

function firstFile(form: FormData, ...keys: string[]) {
  for (const key of keys) {
    const value = form.get(key);
    if (value instanceof File && value.size > 0) return value;
  }
  return null;
}

function isSupportedUpload(file: File, extensions: readonly string[], mimeTypes: Set<string>) {
  const lowerCaseName = file.name.toLowerCase();
  return mimeTypes.has(file.type) || extensions.some((extension) => lowerCaseName.endsWith(extension));
}

async function readBackendPayload(response: Response) {
  const raw = await response.text().catch(() => '');
  if (!raw) return { payload: null, raw: '' };
  try {
    return { payload: JSON.parse(raw), raw };
  } catch {
    return { payload: null, raw };
  }
}

export async function submitFirstBatch(request: Request, cookies: Cookies) {
  const backendUrl = requireBackendUrl();
  const form = await request.formData();
  const sourceType = firstString(form, 'sourceType', 'source_type');
  const companyName = firstString(form, 'companyName', 'company_name');
  const websiteUrl = firstString(form, 'websiteUrl', 'website_url');
  const audience = firstString(form, 'audience') || 'Investment Committee';
  const purpose = firstString(form, 'purpose') || 'Initial diligence review';
  const founderName = firstString(form, 'founderName', 'founder_name');
  const notes = firstString(form, 'notes');
  const teamNotes = firstString(form, 'teamNotes', 'team_notes');
  const logoFile = firstFile(form, 'logoFile', 'logo_file');

  if (!SUPPORTED_FIRST_BATCH_TYPES.has(sourceType)) {
    throw error(400, 'First batch source must be URL branding or logo branding.');
  }
  if (sourceType === 'url_branding' && !websiteUrl) {
    throw error(400, 'A company URL is required for URL branding.');
  }
  if (sourceType === 'logo_branding' && !logoFile) {
    throw error(400, 'A logo file is required for logo branding.');
  }
  if (logoFile && !isSupportedUpload(logoFile, SUPPORTED_LOGO_EXTENSIONS, SUPPORTED_LOGO_MIME_TYPES)) {
    throw error(400, 'Only PNG, JPEG, GIF, and WebP logo uploads are supported.');
  }

  const backendForm = new FormData();
  backendForm.set('source_type', sourceType);
  if (companyName) backendForm.set('company_name', companyName);
  if (websiteUrl) backendForm.set('website_url', websiteUrl);
  backendForm.set('audience', audience);
  backendForm.set('purpose', purpose);
  if (founderName) backendForm.set('founder_name', founderName);
  if (notes) backendForm.set('notes', notes);
  if (teamNotes) backendForm.set('team_notes', teamNotes);
  if (logoFile) backendForm.set('logo_file', logoFile);

  let response: Response;
  try {
    response = await fetch(`${backendUrl}${deckProductApiPath('/decks/first-batch')}`, {
      method: 'POST',
      headers: requireBackendAuthHeaders(cookies),
      body: backendForm
    });
  } catch (fetchError) {
    return json(
      { message: fetchError instanceof Error ? fetchError.message : 'First batch backend fetch failed.' },
      { status: 503 }
    );
  }

  const { payload, raw } = await readBackendPayload(response);
  if (!response.ok) {
    return json(
      {
        message: extractErrorMessage(payload, raw || 'First batch creation failed.'),
        backendStatus: response.status,
        backendDetail: payload?.detail ?? payload?.message ?? payload?.error ?? null,
        sourceType,
        hasWebsiteUrl: Boolean(websiteUrl),
        hasLogoFile: Boolean(logoFile)
      },
      { status: response.status }
    );
  }

  return json(
    {
      ok: true,
      workspaceId: payload?.workspaceId ?? payload?.workspace_id ?? null,
      deckId: payload?.deckId ?? payload?.deck_id ?? null,
      batchId: payload?.batchId ?? payload?.batch_id ?? null,
      sourceType: payload?.sourceType ?? payload?.source_type ?? sourceType,
      generationStatus: payload?.generationStatus ?? payload?.generation_status ?? 'ready',
      nextUrl: payload?.nextUrl ?? payload?.next_url ?? null,
      confirmation: payload?.confirmation ?? null,
      workspace: payload?.workspace ?? null
    },
    { status: response.status }
  );
}
