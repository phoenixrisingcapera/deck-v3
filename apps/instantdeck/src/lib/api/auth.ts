import { fetchApiJsonOrThrow } from '$lib/api/apiError';

/*
  This file is the frontend auth API client.

  It calls local SvelteKit auth endpoints:
  - /api/auth/session/validate
  - /api/auth/sign-in
  - /api/auth/sign-up
  - /api/auth/reset-password

  It returns plain typed objects on success and structured ApiClientError errors on:
  - non-2xx backend responses
  - fetch/network transport failures
  - parse failures (wrapped as backend/backend-like message).
*/

const AUTH_API_BASE = '/api/auth';

type InspectionResponse = {
  enabled: boolean;
  active: boolean;
  founderEmail: string | null;
  hasPassword: boolean;
  backendConfigured: boolean;
  bypasses: {
    routeAccess: boolean;
    billing: boolean;
    providers: boolean;
  };
};

type SessionValidationResponse = {
  valid: boolean;
  user?: {
    id: string;
    email: string;
    name: string;
    role: 'super_admin' | 'admin' | 'user' | 'general';
    preferredTheme: 'light' | 'dark';
    billingPlan: string;
    permissions: string[];
    
  };
  inspection?: InspectionResponse;
};

export function validateSession(): Promise<SessionValidationResponse> {
  return requestAuthRoute<SessionValidationResponse>('/session/validate');
}

type SignInRequest = {
  email: string;
  password: string;
};

type SignUpRequest = {
  name: string;
  email: string;
  password: string;
  companyName?: string;
  role?: 'general' | 'user';
  acceptedTerms: boolean;
};

type AuthRouteResponse = {
  nextUrl: string;
  user: {
    id: string;
    email: string;
    name: string;
    role: 'super_admin' | 'admin' | 'user' | 'general';
  };
  workspace?: {
    id: string;
    name: string;
  };
};

async function requestAuthRoute<T>(path: string, body?: unknown): Promise<T> {
  const method = body ? 'POST' : 'GET';
  const url = `${AUTH_API_BASE}${path}`;
  return await fetchApiJsonOrThrow<T>(
    url,
    {
      method,
      credentials: 'include',
      headers: body ? { 'content-type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined
    },
    'Authentication request failed.'
  );
}

export function signIn(payload: SignInRequest): Promise<AuthRouteResponse> {
  return requestAuthRoute<AuthRouteResponse>('/sign-in', payload);
}

export function signUp(payload: SignUpRequest): Promise<AuthRouteResponse> {
  return requestAuthRoute<AuthRouteResponse>('/sign-up', payload);
}

type ChangePasswordRequest = {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
};

type ChangePasswordResponse = {
  status: 'ok';
};

export function changePassword(payload: ChangePasswordRequest): Promise<ChangePasswordResponse> {
  return requestAuthRoute<ChangePasswordResponse>('/reset-password', {
    current_password: payload.currentPassword,
    new_password: payload.newPassword,
    confirm_password: payload.confirmPassword,
  });
}
