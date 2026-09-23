import type { RequestHandler } from './$types';
import { publicSeoPages } from '$lib/seo/pages';
import { SITE } from '$lib/seo/seo';

export const GET: RequestHandler = async () => {
  const now = new Date().toISOString();
  const urls = Object.values(publicSeoPages)
    .filter((page) => !page.noindex)
    .map((page) => ({
      loc: `${SITE.url}${page.canonicalPath}`,
      lastmod: now,
      changefreq: page.changeFrequency,
      priority: typeof page.priority === 'number' ? page.priority.toFixed(1) : null
    }));

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls
  .map(
    (url) => `  <url>
    <loc>${url.loc}</loc>
    <lastmod>${url.lastmod}</lastmod>
${url.changefreq ? `    <changefreq>${url.changefreq}</changefreq>
` : ''}${url.priority ? `    <priority>${url.priority}</priority>
` : ''}  </url>`
  )
  .join('\n')}
</urlset>`;

  return new Response(body, {
    headers: {
      'Content-Type': 'application/xml',
      'Cache-Control': 'max-age=3600'
    }
  });
};
