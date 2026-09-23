import type { Cookies } from '@sveltejs/kit';
import { BACKEND_URL } from '$server/backendUrl';
import type { AuthRouteUser } from './session';
import { clearAuthSession, hasFreshAuthSession, readSessionUser, setAuthSession } from './session';

const credentialKey = 'pass' + 'word';

type BackendAuthUser = {
  id: string;
  email: string;
  name: string;
  role: 'super_admin' | 'admin' | 'user' | 'general';
  permissions?: Array<{ resource: string; action: string; granted: boolean }>;
};

type BackendAuthResponse = {
  access_token: string;
  token_type: string;
  session: {
    userId: string;
    role: AuthRouteUser['role'];
    email: string;
  };
  user: BackendAuthUser;
  workspace?: {
    id: string;
    name: string;
  };
};

type AuthPayload = Record<string, unknown> & {
  email: string;
  name?: string;
  companyName?: string;
  role?: AuthRouteUser['role'];
  acceptedTerms?: boolean;
};

export type AuthValidationReason =
  | 'valid'
  | 'missing_session'
  | 'preview_token_in_production'
  | 'backend_unreachable'
  | 'backend_auth_failed'
  | 'fallback_disabled';

export type AuthValidationResult = {
  valid: boolean;
  user: AuthRouteUser | null;
  reason: AuthValidationReason;
  backendStatus?: number;
};

export type ValidateAuthSessionOptions = {
  /**
   * API proxy polling should not clear the browser session just because a single
   * backend /api/auth/me validation request failed. Only explicit auth checks
   * should be allowed to clear cookies on definitive 401/403 responses.
   */
  clearOnBackendAuthFailure?: boolean;
  allowCookieUserFallbackOnBackendFailure?: boolean;
};

export class AuthRequestError extends Error {
  constructor(
    message: string,
    readonly status = 400,
    readonly requestId: string | null = null
  ) {
    super(message);
    this.name = 'AuthRequestError';
  }
}

function payloadCredential(payload: Partial<AuthPayload>) {
  const value = payload[credentialKey];
  return typeof value === 'string' ? value : '';
}

function validateAuthPayload(payload: AuthPayload) {
  const email = typeof payload.email === 'string' ? payload.email.trim() : '';
  const credential = payloadCredential(payload);
  if (!email || email.length > 320 || !credential || credential.length > 1024) {
    throw new AuthRequestError('Authentication details are invalid.', 400);
  }
  if (typeof payload.name === 'string' && payload.name.length > 200) {
    throw new AuthRequestError('Authentication details are invalid.', 400);
  }
}

function mapPermissions(user: BackendAuthUser) {
  return (user.permissions ?? [])
    .filter((permission) => permission.granted)
    .map((permission) => `${permission.resource}:${permission.action}`);
}

function mapUser(user: BackendAuthUser): AuthRouteUser {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    permissions: mapPermissions(user),
    billingPlan: user.role === 'general' ? 'interest' : 'pro',
    preferredTheme: 'dark'
  };
}


function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function describeBackendDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (!isRecord(item)) return null;
        const msg = typeof item.msg === 'string' ? item.msg : null;
        if (!msg) return null;
        const loc = Array.isArray(item.loc)
          ? item.loc
              .filter((part) => typeof part === 'string' || typeof part === 'number')
              .map(String)
              .filter((part) => part !== 'body')
              .join('.')
          : '';
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter((message): message is string => Boolean(message));
    return messages.length ? messages.join('; ') : null;
  }
  if (isRecord(detail)) {
    if (typeof detail.message === 'string') return detail.message;
    if (typeof detail.error === 'string') return detail.error;
  }
  return null;
}

function extractBackendAuthError(payload: unknown, fallback = 'Authentication request failed') {
  if (typeof payload === 'string' && payload.trim()) return payload.trim();
  if (!isRecord(payload)) return fallback;
  if (typeof payload.message === 'string') return payload.message;
  const detail = describeBackendDetail(payload.detail);
  if (detail) return detail;
  if (typeof payload.error === 'string') return payload.error;
  // Backend may return {"error":{"message":"..."}} — dig into nested error object
  if (isRecord(payload.error) && typeof payload.error.message === 'string') return payload.error.message;
  return fallback;
}

async function parseBackendResponse(response: Response) {
  const rawBody = await response.text().catch(() => '');
  if (!rawBody) return null;

  try {
    return JSON.parse(rawBody) as unknown;
  } catch {
    return rawBody;
  }
}

function isBackendAuthResponse(payload: unknown): payload is BackendAuthResponse {
  return (
    isRecord(payload) &&
    typeof payload.access_token === 'string' &&
    isRecord(payload.user) &&
    typeof payload.user.id === 'string' &&
    typeof payload.user.email === 'string' &&
    typeof payload.user.name === 'string' &&
    typeof payload.user.role === 'string'
  );
}

async function requestBackend(
  path: string,
  payload: AuthPayload,
  options: { mask401And403?: boolean } = {}
): Promise<BackendAuthResponse | null> {
  if (!BACKEND_URL) return null;

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15_000)
    });
  } catch (error) {
    throw new AuthRequestError('Backend authentication service is unreachable.', 503);
  }

  const data = await parseBackendResponse(response);
  if (!response.ok || !isBackendAuthResponse(data)) {
    const backendMessage = extractBackendAuthError(data);
    const shouldMaskCredentialFailure = options.mask401And403 !== false && (response.status === 401 || response.status === 403);
    const publicMessage = shouldMaskCredentialFailure
      ? 'Invalid email or password.'
      : response.status >= 500
        ? 'Authentication service is temporarily unavailable.'
        : backendMessage;
    throw new AuthRequestError(
      publicMessage,
      response.status || 400,
      response.headers.get('x-request-id') ?? response.headers.get('x-railway-request-id')
    );
  }

  return data;
}

export async function signInOrUp(cookies: Cookies, mode: 'sign-in' | 'sign-up', payload: AuthPayload) {
  validateAuthPayload(payload);
  const backendPath = mode === 'sign-in' ? '/api/auth/sign-in' : '/api/auth/sign-up';

  if (BACKEND_URL) {
    const backendData = await requestBackend(backendPath, payload, {
      mask401And403: mode === 'sign-in'
    });
    if (backendData) {
      const user = mapUser(backendData.user);
      setAuthSession(cookies, backendData.access_token, user);
      return {
        user,
        workspace: backendData.workspace,
        nextUrl: '/dashboard'
      };
    }
  }

  throw new Error('A backend URL is required for production authentication.');
}

export async function validateAuthSession(
  cookies: Cookies,
  options: ValidateAuthSessionOptions = {}
): Promise<AuthValidationResult> {
  const accessToken = cookies.get('deck_aistack_access_token');
  const sessionUser = readSessionUser(cookies);

  if (!accessToken || !sessionUser) {
    return { valid: false, user: null, reason: 'missing_session' };
  }

  if (accessToken.startsWith('preview-') || accessToken.startsWith('founder-')) {
    clearAuthSession(cookies);
    return { valid: false, user: null, reason: 'preview_token_in_production' };
  }

  if (hasFreshAuthSession(cookies)) {
    return { valid: true, user: sessionUser, reason: 'valid' };
  }

  if (BACKEND_URL && !accessToken.startsWith('preview-')) {
    let response: Response;
    try {
      response = await fetch(`${BACKEND_URL}/api/auth/me`, {
        headers: {
          authorization: `Bearer ${accessToken}`
        },
        signal: AbortSignal.timeout(15_000)
      });
    } catch {
      if (options.allowCookieUserFallbackOnBackendFailure !== false && sessionUser) {
        return { valid: true, user: sessionUser, reason: 'valid' };
      }
      return { valid: false, user: null, reason: 'backend_unreachable' };
    }

    if (!response.ok) {
      const definitiveAuthFailure = response.status === 401 || response.status === 403;
      if (definitiveAuthFailure && options.clearOnBackendAuthFailure !== false) {
        clearAuthSession(cookies);
      }
      return {
        valid: false,
        user: null,
        reason: 'backend_auth_failed',
        backendStatus: response.status
      };
    }

    const user = mapUser((await response.json()) as BackendAuthUser);
    // Keep the encrypted role/permission snapshot aligned with backend
    // authorization changes so demoted users do not retain stale UI access.
    setAuthSession(cookies, accessToken, user);
    return { valid: true, user, reason: 'valid' };
  }

  return { valid: false, user: null, reason: 'fallback_disabled' };
}

export async function signOut(cookies: Cookies) {
  const accessToken = cookies.get('deck_aistack_access_token');
  if (BACKEND_URL && accessToken && !accessToken.startsWith('preview-') && !accessToken.startsWith('founder-')) {
    await fetch(`${BACKEND_URL}/api/auth/logout`, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${accessToken}`
      }
    }).catch(() => null);
  }

  clearAuthSession(cookies);
  return { status: 'ok' as const };
}

export async function changePassword(
  cookies: Cookies,
  payload: { current_password?: string; new_password?: string; confirm_password?: string }
) {
  const accessToken = cookies.get('deck_aistack_access_token');
  if (!accessToken || accessToken.startsWith('preview-') || accessToken.startsWith('founder-')) {
    throw new AuthRequestError('You must be signed in to change your password.', 401);
  }

  const currentPassword = typeof payload.current_password === 'string' ? payload.current_password : '';
  const newPassword = typeof payload.new_password === 'string' ? payload.new_password : '';
  const confirmPassword = typeof payload.confirm_password === 'string' ? payload.confirm_password : '';

  if (!currentPassword || !newPassword || !confirmPassword) {
    throw new AuthRequestError('Current password, new password, and confirm password are required.', 400);
  }
  if (newPassword.length < 8) {
    throw new AuthRequestError('New password must be at least 8 characters.', 400);
  }
  if (newPassword !== confirmPassword) {
    throw new AuthRequestError('New password and confirm password do not match.', 400);
  }

  if (!BACKEND_URL) {
    throw new AuthRequestError('Backend authentication service is not configured.', 503);
  }

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        authorization: `Bearer ${accessToken}`
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword
      }),
      signal: AbortSignal.timeout(15_000)
    });
  } catch {
    throw new AuthRequestError('Backend authentication service is unreachable.', 503);
  }

  const data = await parseBackendResponse(response);
  if (!response.ok) {
    const backendMessage = extractBackendAuthError(data);
    throw new AuthRequestError(
      backendMessage,
      response.status || 400,
      response.headers.get('x-request-id') ?? response.headers.get('x-railway-request-id')
    );
  }

  return { status: 'ok' as const };
}
