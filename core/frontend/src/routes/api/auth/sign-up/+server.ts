import { json, redirect } from '@sveltejs/kit';
import { AuthRequestError, signInOrUp } from '$server/auth/authService';

export function GET() {
  throw redirect(303, '/auth/sign-up');
}

export async function POST({ request, cookies }) {
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return json({ message: 'Authentication payload must be a JSON object.' }, { status: 400 });
  }

  try {
    const result = await signInOrUp(cookies, 'sign-up', payload as Parameters<typeof signInOrUp>[2]);
    return json(result, { status: 201 });
  } catch (err) {
    const status = err instanceof AuthRequestError ? err.status : 400;
    const requestId = err instanceof AuthRequestError ? err.requestId : null;
    const headers = requestId ? { 'x-request-id': requestId } : undefined;
    return json({ message: err instanceof Error ? err.message : 'Could not create account' }, { status, headers });
  }
}
