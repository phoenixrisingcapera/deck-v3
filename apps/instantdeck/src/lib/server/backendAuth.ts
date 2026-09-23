import type { Cookies } from '@sveltejs/kit';
import { error } from '@sveltejs/kit';
import { AUTH_ACCESS_COOKIE } from '$server/auth/session';

export function getBackendAccessToken(cookies: Cookies) {
  const token = cookies.get(AUTH_ACCESS_COOKIE);
  if (!token || token.startsWith('preview-') || token.startsWith('founder-')) {
    return null;
  }

  return token;
}

export function requireBackendAuthHeaders(cookies: Cookies): HeadersInit {
  const token = getBackendAccessToken(cookies);
  if (!token) {
    throw error(401, 'Authentication is required for this backend request.');
  }

  return { authorization: `Bearer ${token}` };
}

export function optionalBackendAuthHeaders(cookies: Cookies): HeadersInit {
  const token = getBackendAccessToken(cookies);
  return token ? { authorization: `Bearer ${token}` } : {};
}
