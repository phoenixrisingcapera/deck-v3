import { json, type RequestHandler } from '@sveltejs/kit';
import { deckProductApiPath } from '$lib/contracts';
import { submitWorkflowCommand } from '$server/services/workflowCommandService';

export const POST: RequestHandler = async ({ request, fetch, cookies, params }) => {
  const payload = await request.json().catch(() => ({}));
  const accepted = await submitWorkflowCommand<Record<string, unknown>>(
    fetch,
    cookies,
    deckProductApiPath(`/decks/${params.deckId}/workflows/export`),
    'Could not start export workflow.',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: payload?.type ?? payload?.exportType,
        exportType: payload?.exportType ?? payload?.type,
        format: payload?.format ?? 'html',
        designVersionId: payload?.designVersionId ?? null,
        idempotencyKey: payload?.idempotencyKey
      })
    }
  );

  return json(accepted);

  // DISABLED: product export workflow submission is intentionally blocked during
  // testing mode to keep release control with admin.
  // const payload = await request.json().catch(() => ({}));
  // const accepted = await submitWorkflowCommand<Record<string, unknown>>(
  //   fetch,
  //   cookies,
  //   deckProductApiPath(`/decks/${params.deckId}/workflows/export`),
  //   'Could not start export workflow.',
  //   {
  //     method: 'POST',
  //     headers: { 'content-type': 'application/json' },
  //     body: JSON.stringify({
  //       type: payload?.type ?? payload?.exportType,
  //       exportType: payload?.exportType ?? payload?.type,
  //       idempotencyKey: payload?.idempotencyKey
  //     })
  //   }
  // );
  //
  // return json(accepted);
};
