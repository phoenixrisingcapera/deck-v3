import { json } from '@sveltejs/kit';
import { submitWorkspaceSlideFeedback } from '$server/services/generatedWorkspaceService';

export async function POST({ params, request, cookies }) {
  const payload = await request.json();
  const response = await submitWorkspaceSlideFeedback(params.deckId, params.slideId, payload, cookies);

  return json(response);
}
