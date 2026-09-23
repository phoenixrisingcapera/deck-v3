import { json, type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { submitWorkflowCommand } from '$server/services/workflowCommandService';

export const POST: RequestHandler = async ({ request, fetch, cookies, params }) => {
  const payload = await request.json();
  const accepted = await submitWorkflowCommand<Record<string, unknown>>(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/workflows/smart-deck-generation/retry-failed`),
    'Failed slides could not be retried.',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }
  );
  return json(accepted);
};
