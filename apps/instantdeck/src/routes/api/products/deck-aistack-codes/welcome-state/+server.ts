import { proxyBackendJson } from '$server/backendApi';
import { deckProductApiPath } from '$lib/contracts';

export async function GET({ fetch, cookies }) {
  return proxyBackendJson(
    fetch,
    cookies,
    deckProductApiPath('/welcome-state'),
    {},
    'Could not load welcome state.'
  );
}
