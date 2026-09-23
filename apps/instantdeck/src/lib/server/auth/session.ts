import { env } from '$env/dynamic/private';
import type { Cookies } from '@sveltejs/kit';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

export type AuthRouteUser = {
  id: string;
  email: string;
  name: string;
  role: 'super_admin' | 'admin' | 'user' | 'general';
  permissions: string[];
  billingPlan: string;
  preferredTheme: 'light' | 'dark';
  
};

export const AUTH_ACCESS_COOKIE = 'deck_aistack_access_token';
export const AUTH_USER_COOKIE = 'deck_aistack_session_user';
export const AUTH_FRESH_COOKIE = 'deck_aistack_session_fresh_at';
const AUTH_FRESH_WINDOW_MS = 5 * 60 * 1000;

const DEFAULT_COOKIE_OPTIONS = {
  httpOnly: true,
  sameSite: 'lax' as const,
  secure: env.NODE_ENV === 'production',
  path: '/'
};

const DELETE_COOKIE_OPTIONS = {
  path: '/',
  sameSite: 'lax' as const,
  secure: env.NODE_ENV === 'production'
};

function sessionKey() {
  const secret = env.AUTH_SECRET_KEY || env.DECK_AISTACK_CREDENTIAL_SECRET;
  if (!secret) throw new Error('AUTH_SECRET_KEY must be configured to use authenticated sessions.');
  return createHash('sha256').update(secret).digest();
}

function encodeUser(user: AuthRouteUser) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', sessionKey(), iv);
  const encrypted = Buffer.concat([cipher.update(JSON.stringify(user), 'utf8'), cipher.final()]);
  return [iv, cipher.getAuthTag(), encrypted].map((part) => part.toString('base64url')).join('.');
}

function decodeUser(value: string | undefined): AuthRouteUser | null {
  if (!value) return null;

  try {
    const [ivValue, tagValue, encryptedValue] = value.split('.');
    if (!ivValue || !tagValue || !encryptedValue) return null;
    const decipher = createDecipheriv('aes-256-gcm', sessionKey(), Buffer.from(ivValue, 'base64url'));
    decipher.setAuthTag(Buffer.from(tagValue, 'base64url'));
    const parsed = JSON.parse(Buffer.concat([
      decipher.update(Buffer.from(encryptedValue, 'base64url')),
      decipher.final()
    ]).toString('utf8')) as AuthRouteUser;
    return parsed;
  } catch {
    return null;
  }
}

export function readSessionUser(cookies: Cookies) {
  return decodeUser(cookies.get(AUTH_USER_COOKIE));
}

export function hasFreshAuthSession(cookies: Cookies) {
  const value = cookies.get(AUTH_FRESH_COOKIE);
  if (!value) return false;

  const issuedAt = Number.parseInt(value, 10);
  if (!Number.isFinite(issuedAt)) return false;

  return Date.now() - issuedAt <= AUTH_FRESH_WINDOW_MS;
}

export function setAuthSession(cookies: Cookies, accessToken: string, user: AuthRouteUser) {
  cookies.set(AUTH_ACCESS_COOKIE, accessToken, DEFAULT_COOKIE_OPTIONS);
  cookies.set(AUTH_USER_COOKIE, encodeUser(user), DEFAULT_COOKIE_OPTIONS);
  cookies.set(AUTH_FRESH_COOKIE, String(Date.now()), DEFAULT_COOKIE_OPTIONS);
}

export function clearAuthSession(cookies: Cookies) {
  cookies.delete(AUTH_ACCESS_COOKIE, DELETE_COOKIE_OPTIONS);
  cookies.delete(AUTH_USER_COOKIE, DELETE_COOKIE_OPTIONS);
  cookies.delete(AUTH_FRESH_COOKIE, DELETE_COOKIE_OPTIONS);
}
