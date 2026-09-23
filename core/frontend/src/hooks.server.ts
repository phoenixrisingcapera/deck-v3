import { error, type Handle, type HandleServerError } from '@sveltejs/kit';
import { existsSync, readFileSync } from 'node:fs';
import { readSessionUser } from '$lib/server/auth/session';
import { validateAuthSession } from '$lib/server/auth/authService';
import { reportFailureTicketToBackend } from '$lib/server/failureTickets';
import { DECK_PRODUCT_API_PREFIX } from '$lib/contracts';
import { dashboardImageCspSources } from '$lib/dashboard/imagePolicy.server';
import { validateProductionConfiguration } from '$lib/server/backendUrl';
import { BACKEND_URL } from '$lib/server/backendUrl';
import { INSTANT_HTML_RENDERER_ORIGIN } from '$lib/server/instantHtmlRendererOrigin';
import { withInstantHtmlFrameSource } from '$lib/config/instantHtmlRendererOrigin.js';

const productionConfiguration = validateProductionConfiguration();
if (existsSync('BUILD_REVISION')) {
  console.info(`deck_build_revision=${readFileSync('BUILD_REVISION', 'utf8').trim()}`);
}
const MAX_JSON_MUTATION_BYTES = 10 * 1024 * 1024;
if (!productionConfiguration.ok) {
  throw new Error(`Frontend production configuration is invalid: ${productionConfiguration.errors.join(' ')}`);
}

export const handle: Handle = async ({ event, resolve }) => {
  const isApiRequest = event.url.pathname.startsWith('/api/');
  const isDeckProductApiRequest = event.url.pathname.startsWith(DECK_PRODUCT_API_PREFIX);

  if (isDeckProductApiRequest) {
    // Product proxy routes forward the existing backend bearer token from the
    // cookie. Do not call backend /api/auth/me before every polling request;
    // a transient validation failure can otherwise clear the session cookie.
    event.locals.sessionUser = readSessionUser(event.cookies);
  } else if (isApiRequest) {
    const session = await validateAuthSession(event.cookies, { clearOnBackendAuthFailure: false });
    event.locals.sessionUser = session.user ?? readSessionUser(event.cookies);
  } else {
    const session = await validateAuthSession(event.cookies);
    event.locals.sessionUser = session.user ?? readSessionUser(event.cookies);
  }

  // All deck API routes require an authenticated session before they can
  // reach the backend. The backend bearer token remains the authority for
  // verifying that this user owns or may access the requested deck ID.
  const isProductDeckApiRequest = event.url.pathname.startsWith(`${DECK_PRODUCT_API_PREFIX}/decks/`);
  if (
    (event.url.pathname === '/api/decks' || event.url.pathname.startsWith('/api/decks/') || isProductDeckApiRequest) &&
    !event.locals.sessionUser
  ) {
    throw error(401, 'Authentication is required for deck access.');
  }

  // SameSite cookies are not a complete CSRF defense for every browser or
  // deployment combination. Reject explicitly cross-origin API mutations when
  // the browser supplies an Origin header, while allowing server-to-server
  // calls that do not carry one.
  if (isApiRequest && !['GET', 'HEAD', 'OPTIONS'].includes(event.request.method)) {
    const origin = event.request.headers.get('origin');
    if (origin && origin !== event.url.origin) {
      throw error(403, 'Cross-origin API requests are not allowed.');
    }

    const contentType = event.request.headers.get('content-type') ?? '';
    const contentLength = Number.parseInt(event.request.headers.get('content-length') ?? '', 10);
    if (contentType.includes('application/json') && Number.isFinite(contentLength) && contentLength > MAX_JSON_MUTATION_BYTES) {
      throw error(413, 'Request body is too large.');
    }
  }

  const response = await resolve(event);

  // Prevent browsers/proxies from holding stale SvelteKit HTML that points to
  // previous _app/immutable build assets after Railway deploys.
  const contentType = response.headers.get('content-type') ?? '';
  if (!event.url.pathname.startsWith('/_app/') && contentType.includes('text/html')) {
    response.headers.set('cache-control', 'no-store, max-age=0, must-revalidate');
    response.headers.set('pragma', 'no-cache');
    response.headers.set('expires', '0');
  }

  if (!response.headers.has('content-security-policy')) {
    // Apply a complete baseline policy rather than setting only img-src.
    const backendOrigin = BACKEND_URL ? new URL(BACKEND_URL).origin : '';
    response.headers.set(
      'content-security-policy',
      [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "script-src 'self'",
         // Svelte components use runtime style attributes for dynamic visual
         // states. Keep scripts nonce-protected, but allow those styles so the
         // product controls remain visible under the production CSP.
         "style-src 'self' 'unsafe-inline'",
        `img-src 'self' data: blob: ${dashboardImageCspSources().join(' ')}`,
        `connect-src 'self' ${backendOrigin}`,
        "font-src 'self' data:",
        "worker-src 'self' blob:",
        `frame-src ${INSTANT_HTML_RENDERER_ORIGIN ?? "'none'"}`
      ].join('; ')
    );
  } else {
    response.headers.set(
      'content-security-policy',
      withInstantHtmlFrameSource(response.headers.get('content-security-policy') ?? '', INSTANT_HTML_RENDERER_ORIGIN)
    );
  }

  return response;
};

export const handleError: HandleServerError = async ({ error, event, status, message }) => {
  const errorValue = error instanceof Error ? error : null;
  await reportFailureTicketToBackend(event.fetch, event.cookies, {
    route: event.route.id,
    pageUrl: event.url.href,
    statusCode: status,
    userId: event.locals.sessionUser?.id ?? null,
    userEmail: event.locals.sessionUser?.email ?? null,
    errorName: errorValue?.name ?? 'ServerLoadError',
    errorMessage: errorValue?.message ?? message,
    errorStack: errorValue?.stack ?? null,
    severity: status >= 500 ? 'high' : 'medium',
    source: 'loader',
    context: {
      method: event.request.method,
      pathname: event.url.pathname
    }
  });

  return {
    message: 'Something went wrong. We have recorded the issue for review.'
  };
};
