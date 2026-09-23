import { json } from '@sveltejs/kit';
import { fetchWorkflowJob } from '$server/deckWorkflowProxy';

export async function GET({ params, fetch, cookies }) {
  const payload = await fetchWorkflowJob(fetch, cookies, params.jobId);
  return json(payload);
}
