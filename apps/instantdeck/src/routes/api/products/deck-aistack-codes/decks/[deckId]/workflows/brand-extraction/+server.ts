import { json } from '@sveltejs/kit';
import { readBrandExtractionSubmission, submitBrandExtractionWorkflow } from '$server/services/brandExtractionService';

export async function POST({ params, request, fetch, cookies }) {
  const submission = await readBrandExtractionSubmission(request);
  const { payload, status } = await submitBrandExtractionWorkflow(fetch, cookies, params.deckId, submission);
  return json(payload, { status });
}
