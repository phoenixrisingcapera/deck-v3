import { requireBackendUrl } from '$server/backendApi';

export async function GET({ params, fetch }) {
  const backendUrl = requireBackendUrl();
  const shareId = encodeURIComponent(params.shareId);
  const shareToken = encodeURIComponent(params.shareToken);
  const response = await fetch(`${backendUrl}/api/public/deck-shares/${shareId}/${shareToken}`, {
    headers: { accept: 'text/html' }
  }).catch(() => null);

  if (!response) {
    return new Response('This shared deck is temporarily unavailable.', {
      status: 503,
      headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' }
    });
  }
  if (!response.ok) {
    return new Response('This share link is invalid, expired, or revoked.', {
      status: response.status === 404 ? 404 : 502,
      headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' }
    });
  }

  return new Response(response.body, {
    status: 200,
    headers: {
      'content-type': 'text/html; charset=utf-8',
      'content-disposition': 'inline',
      'cache-control': 'private, no-store, max-age=0',
      'referrer-policy': 'no-referrer',
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'DENY',
      'content-security-policy': response.headers.get('content-security-policy') ?? "frame-ancestors 'none'; base-uri 'none'"
    }
  });
}
