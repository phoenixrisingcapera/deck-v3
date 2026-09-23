import { env } from '$env/dynamic/private';
import { dev } from '$app/environment';

export const BACKEND_URL_ENV_NAME = 'DECK_AISTACK_BACKEND_URL' as const;
// Compatibility aliases are still supported for older deploys, but the current
// production deployment should set only DECK_AISTACK_BACKEND_URL when possible.
export const BACKEND_URL_ENV_NAMES = [
  BACKEND_URL_ENV_NAME,
  'BACKEND_URL',
  'API_BASE_URL',
  'PUBLIC_API_BASE_URL',
  'DECK_BACKEND_URL',
  'PUBLIC_DECK_AISTACK_BACKEND_URL'
] as const;

type BackendEnvSource = Record<string, string | undefined>;

function cleanBackendUrl(value: string | undefined) {
  const raw = (value ?? '').trim().replace(/\/+$/, '');
  if (!raw) return '';

  // Railway users often enter `api.deck.aistack.codes` instead of a fully
  // qualified URL. Node's server-side fetch requires a protocol, so normalize
  // bare hostnames here instead of crashing auth with "Failed to parse URL".
  if (/^https?:\/\//i.test(raw)) {
    return raw;
  }

  return `https://${raw}`;
}

function resolveBackendUrl(envSource: BackendEnvSource = env) {
  for (const name of BACKEND_URL_ENV_NAMES) {
    const resolved = cleanBackendUrl(envSource[name]);
    if (resolved) return resolved;
  }
  return '';
}

export const BACKEND_URL = resolveBackendUrl();

export function validateProductionConfiguration(): { ok: boolean; errors: string[] } {
  if (dev) return { ok: true, errors: [] };

  const errors: string[] = [];

  if (!BACKEND_URL) {
    // Missing backend configuration is allowed at process start so Railway can
    // boot the frontend and serve non-backend pages. Backend-dependent routes
    // still call requireBackendUrl(), which returns a route-level 503 instead
    // of killing miniatures, upload, or Smart Deck UI boot globally.
    return { ok: true, errors: [] };
  } else {
    try {
      const parsed = new URL(BACKEND_URL);
      if (parsed.protocol !== 'https:') {
        errors.push(`Backend URL must use https in production. Current ${BACKEND_URL_ENV_NAME} resolves to ${BACKEND_URL}.`);
      }
      if (['localhost', '127.0.0.1', '0.0.0.0'].includes(parsed.hostname)) {
        errors.push(`Backend URL must not point at a local host in production. Current ${BACKEND_URL_ENV_NAME} resolves to ${BACKEND_URL}.`);
      }
      if (parsed.pathname && parsed.pathname !== '/') {
        errors.push(`Backend URL must be an origin only, without an API path. Current ${BACKEND_URL_ENV_NAME} resolves to ${BACKEND_URL}.`);
      }
    } catch {
      errors.push(`Backend URL is malformed. Current ${BACKEND_URL_ENV_NAME} resolves to ${BACKEND_URL}.`);
    }
  }

  return { ok: errors.length === 0, errors };
}
