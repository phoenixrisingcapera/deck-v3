import { json } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { readApplyDesignVersionSubmission, submitWorkflowCommand } from '$server/services/workflowCommandService';

export async function POST({ params, request, fetch, cookies }) {
  const payload = await readApplyDesignVersionSubmission(request);
  const accepted = await submitWorkflowCommand<Record<string, unknown>>(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/workflows/apply-design-version`),
    'Design version apply failed.',
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        designVersionId: payload.designVersionId,
        idempotencyKey: `apply:${params.deckId}:${payload.designVersionId}`
      })
    }
  );

  return json(accepted);
}
