import { json } from '@sveltejs/kit';
import { fetchWorkflowState } from '$server/deckWorkflowProxy';

export async function GET({ params, fetch, cookies }) {
  try {
    const payload = await fetchWorkflowState(fetch, cookies, params.deckId);
    return json(payload);
  } catch (error) {
    const status = typeof error === 'object' && error !== null && 'status' in error && typeof error.status === 'number' ? error.status : 500;
    const message = error instanceof Error && error.message ? error.message : 'Could not load deck workflow state.';
    const requestId =
      typeof error === 'object' && error !== null && 'requestId' in error && typeof error.requestId === 'string'
        ? error.requestId
        : null;
    const backendStatus =
      typeof error === 'object' && error !== null && 'backendStatus' in error && typeof error.backendStatus === 'number'
        ? error.backendStatus
        : null;
    return json(
      {
        ok: false,
        message,
        status,
        requestId,
        failureCategory: backendStatus ? 'backend_response_error' : 'frontend_proxy_error',
        backendStatus
      },
      { status, headers: requestId ? { 'x-request-id': requestId } : undefined }
    );
  }
}
