import { json } from '@sveltejs/kit';
import { BACKEND_URL } from '$server/backendUrl';

export const prerender = false;

export function GET() {
  return json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    configuration: {
      backendUrlConfigured: Boolean(BACKEND_URL)
    }
  });
}
