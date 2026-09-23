import type { RequestHandler } from './$types';
import { SITE } from '$lib/seo/seo';

export const GET: RequestHandler = async () => {
  const body = `User-agent: *
Allow: /

Disallow: /app
Disallow: /dashboard
Disallow: /decks
Disallow: /settings
Disallow: /smart-edit
Disallow: /datasets
Disallow: /insights
Disallow: /exports
Disallow: /team
Disallow: /welcome
Disallow: /welcome_back
Disallow: /sign_in_landing
Disallow: /auth
Disallow: /api

Sitemap: ${SITE.url}/sitemap.xml
`;

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain'
    }
  });
};
