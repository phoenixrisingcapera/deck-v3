import { json } from '@sveltejs/kit';

import { AuthRequestError, changePassword } from '$server/auth/authService';

export function GET() {
  return json({ message: 'Use POST to change your password.' }, { status: 405 });
}

export async function POST({ request, cookies }) {
  const payload = await request.json().catch(() => null);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return json({ message: 'Password change payload must be a JSON object.' }, { status: 400 });
  }

  try {
    const result = await changePassword(cookies, payload);
    return json(result);
  } catch (err) {
    const status = err instanceof AuthRequestError ? err.status : 400;
    const requestId = err instanceof AuthRequestError ? err.requestId : null;
    const headers = requestId ? { 'x-request-id': requestId } : undefined;
    return json({ message: err instanceof Error ? err.message : 'Could not change password' }, { status, headers });
  }
}
