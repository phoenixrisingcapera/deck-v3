import { json } from '@sveltejs/kit';
import { validateAuthSession } from '$server/auth/authService';
import { clearAuthSession } from '$server/auth/session';

export async function GET({ cookies }) {
  const result = await validateAuthSession(cookies);
  const definitiveAuthFailure = result.reason === 'missing_session' || result.reason === 'preview_token_in_production' || result.backendStatus === 401 || result.backendStatus === 403;

  if (!result.valid && definitiveAuthFailure) {
    clearAuthSession(cookies);
  }

  return json({
    valid: result.valid,
    user: result.user,
    reason: result.reason,
    backendStatus: result.backendStatus ?? null,
  });
}
