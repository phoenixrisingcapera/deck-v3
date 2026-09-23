// @ts-check

export const INSTANT_HTML_RENDERER_ORIGIN_ENV = 'INSTANT_HTML_RENDERER_ORIGIN';

/**
 * Resolve one cookieless renderer origin. Invalid values fail closed instead
 * of broadening frame-src or accepting URL paths.
 * @param {Record<string, string | undefined>} source
 */
export function resolveInstantHtmlRendererOrigin(source) {
  const raw = source[INSTANT_HTML_RENDERER_ORIGIN_ENV]?.trim();
  if (!raw) return null;
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`${INSTANT_HTML_RENDERER_ORIGIN_ENV} must be an absolute HTTPS origin.`);
  }
  const localDevelopmentOrigin = parsed.protocol === 'http:'
    && ['127.0.0.1', 'localhost', '::1'].includes(parsed.hostname)
    && source.NODE_ENV !== 'production';
  if (
    (parsed.protocol !== 'https:' && !localDevelopmentOrigin) ||
    parsed.username ||
    parsed.password ||
    parsed.pathname !== '/' ||
    parsed.search ||
    parsed.hash ||
    parsed.origin !== raw.replace(/\/$/, '')
  ) {
    throw new Error(`${INSTANT_HTML_RENDERER_ORIGIN_ENV} must be an exact cookieless HTTPS origin without credentials, path, query, or fragment.`);
  }
  return parsed.origin;
}

/** @param {string} policy @param {string | null} origin */
export function withInstantHtmlFrameSource(policy, origin) {
  const directives = policy.split(';').map((value) => value.trim()).filter(Boolean);
  const filtered = directives.filter((value) => !value.toLowerCase().startsWith('frame-src '));
  filtered.push(`frame-src ${origin ?? "'none'"}`);
  return filtered.join('; ');
}

/** @param {string} renderUrl @param {string | null} configuredOrigin */
export function assertInstantHtmlRenderUrl(renderUrl, configuredOrigin) {
  if (!configuredOrigin) throw new Error('Generated HTML preview is disabled because its cookieless renderer origin is not configured.');
  let parsed;
  try {
    parsed = new URL(renderUrl);
  } catch {
    throw new Error('Generated HTML preview capability returned an invalid render URL.');
  }
  const localDevelopmentOrigin = parsed.protocol === 'http:'
    && ['127.0.0.1', 'localhost', '::1'].includes(parsed.hostname)
    && parsed.origin === configuredOrigin;
  if (parsed.origin !== configuredOrigin || (parsed.protocol !== 'https:' && !localDevelopmentOrigin) || parsed.username || parsed.password) {
    throw new Error('Generated HTML preview capability returned a renderer origin that does not match the configured cookieless renderer.');
  }
  return parsed.href;
}

/**
 * Open synchronously inside the user's click activation. Do not pass the
 * `noopener` feature because some browsers then return null for a tab that did
 * open; sever opener explicitly before any asynchronous capability mint.
 * @param {(url?: string, target?: string) => (Window|null)} openWindow
 */
export function openInstantHtmlPrintPlaceholder(openWindow) {
  const placeholder = openWindow('about:blank', '_blank');
  if (!placeholder) throw new Error('Allow pop-ups, then choose Print / Save as PDF again.');
  try {
    placeholder.opener = null;
  } catch {
    placeholder.close();
    throw new Error('The secure print window could not be isolated.');
  }
  return placeholder;
}
