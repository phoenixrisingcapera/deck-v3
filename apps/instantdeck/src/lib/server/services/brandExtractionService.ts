import { error, type Cookies } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { requireBackendAuthHeaders } from '$server/backendAuth';
import { extractErrorMessage, requireBackendUrl } from '$server/backendApi';

export type BrandExtractionSubmission = {
  companyUrl: string;
  logoFile: File | null;
  brandGuidelinesFile: File | null;
};

export function normalizeCompanyUrl(value: string) {
  const raw = value.trim();
  if (!raw) return '';
  return /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
}

export async function readBrandExtractionSubmission(request: Request): Promise<BrandExtractionSubmission> {
  const contentType = request.headers.get('content-type') ?? '';
  let companyUrl = '';
  let logoFile: File | null = null;
  let brandGuidelinesFile: File | null = null;

  if (contentType.includes('multipart/form-data')) {
    const form = await request.formData();
    companyUrl = normalizeCompanyUrl(String(form.get('companyUrl') ?? ''));
    const maybeLogo = form.get('logoFile');
    logoFile = maybeLogo instanceof File && maybeLogo.size > 0 ? maybeLogo : null;
    const maybeBrandGuidelines = form.get('brandGuidelinesFile');
    brandGuidelinesFile = maybeBrandGuidelines instanceof File && maybeBrandGuidelines.size > 0 ? maybeBrandGuidelines : null;
  } else {
    const payload = await request.json().catch(() => ({}));
    companyUrl = normalizeCompanyUrl(String((payload as { companyUrl?: string | null })?.companyUrl ?? ''));
  }

  if (!companyUrl && !logoFile && !brandGuidelinesFile) {
    throw error(400, 'companyUrl, logoFile, or brandGuidelinesFile is required');
  }

  if (companyUrl) {
    try {
      new URL(companyUrl);
    } catch {
      throw error(400, 'companyUrl must be a valid URL');
    }
  }

  return { companyUrl, logoFile, brandGuidelinesFile };
}

export async function submitBrandExtractionWorkflow(
  fetcher: typeof fetch,
  cookies: Cookies,
  deckId: string,
  submission: BrandExtractionSubmission
): Promise<{ payload: unknown; status: number }> {
  const backendUrl = requireBackendUrl();
  const body = new FormData();
  if (submission.companyUrl) body.set('companyUrl', submission.companyUrl);
  if (submission.logoFile) body.set('logoFile', submission.logoFile);
  if (submission.brandGuidelinesFile) body.set('brandGuidelinesFile', submission.brandGuidelinesFile);

  const response = await fetcher(`${backendUrl}${deckProductApiPath(`/decks/${deckId}/workflows/brand-extraction`)}`, {
    method: 'POST',
    headers: requireBackendAuthHeaders(cookies),
    body
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw error(response.status, extractErrorMessage(payload, 'Brand extraction failed.'));
  }

  return { payload, status: response.status };
}
