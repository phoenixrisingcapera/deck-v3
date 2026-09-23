import { error } from '@sveltejs/kit';

export async function POST({ params, request, fetch, cookies }) {
  const form = await request.formData();
  const slideId = String(form.get('slideId') ?? '').trim();
  const blockId = String(form.get('blockId') ?? '').trim();
  const instruction = String(form.get('instruction') ?? '').trim();
  const audienceType = String(form.get('audienceType') ?? form.get('audience_type') ?? '').trim();
  if (!slideId || !blockId || !instruction || !audienceType) {
    throw error(400, 'Smart Edit requires slideId, blockId, instruction, and audienceType.');
  }
  throw error(410, 'Legacy Smart Edit generation route is disabled. Use the slide-scoped Smart Edit patch route.');
  // DISABLED: this compatibility proxy previously forwarded to the legacy
  // backend /api/decks/{deckId}/smart-edit route. Mounted callers now target
  // /api/decks/{deckId}/slides/{slideId}/smart-edit/patch directly.
}
