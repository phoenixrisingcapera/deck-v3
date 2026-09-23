import { submitFirstBatch } from '$server/services/firstBatchService';

export async function POST({ request, cookies }) {
  return submitFirstBatch(request, cookies);
}
