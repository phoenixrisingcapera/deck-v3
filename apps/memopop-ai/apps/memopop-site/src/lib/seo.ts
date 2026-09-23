/**
 * SEO + OpenGraph system.
 *
 * Single source of truth for everything that lands in <head>:
 *   - <title>, meta description, canonical URL
 *   - Open Graph (og:title, og:description, og:image, og:type, og:url)
 *   - Twitter Card (auto-picks summary_large_image when an image is available)
 *   - article:* tags for entry pages
 *   - JSON-LD Article schema
 *
 * Two resolvers:
 *   - `seoFromPage`  — for pages that aren't backed by a content collection entry
 *   - `seoFromEntry` — for changelog / context-v detail pages; pulls everything
 *                      out of frontmatter and falls back through a sensible chain
 *
 * Image fallback chain for entry pages: banner_image → image → SITE_DEFAULTS.ogImage.
 */

export interface OgImage {
  url: string;
  width?: number;
  height?: number;
  alt?: string;
  type?: string;
}

export interface SeoMeta {
  title: string;
  description: string;
  canonical: string;
  ogType: 'website' | 'article' | 'profile';
  ogImage?: OgImage;
  twitterCard: 'summary' | 'summary_large_image';
  twitterSite?: string;
  twitterCreator?: string;
  noindex?: boolean;
  publishedTime?: string;
  modifiedTime?: string;
  author?: string;
  tags?: string[];
  jsonLd?: Record<string, unknown>;
}

export const SITE_DEFAULTS = {
  name: 'MemoPop AI',
  tagline: 'Multi-agent investment memo orchestrator',
  description:
    'Multi-agent investment memo orchestrator. Turn a company name into an institutional-quality investment memo with 33 specialized AI agents.',
  twitterSite: '@losslessgroup',
  twitterCreator: '@mpstaton',
  ogImage: {
    url: 'https://ik.imagekit.io/xvpgfijuw/Image-Gin/2026-05/MemoPop_AI_banner_image_1778062509552_xx6m5xkS4.webp',
    width: 1200,
    height: 630,
    alt: 'MemoPop AI — multi-agent investment memo orchestrator',
    type: 'image/webp',
  } satisfies OgImage,
} as const;

interface AstroLike {
  url: URL;
  site?: URL;
}

export function resolveCanonical(astro: AstroLike): string {
  const origin = astro.site?.toString().replace(/\/$/, '') ?? 'https://lossless-group.github.io';
  return new URL(astro.url.pathname, origin).toString();
}

export interface SeoFromPageInput {
  astro: AstroLike;
  title: string;
  description?: string;
  ogImage?: OgImage | string | null;
  ogType?: SeoMeta['ogType'];
  noindex?: boolean;
  /** When true, suffixes the title with " — MemoPop AI". Defaults to true unless title already contains the brand. */
  suffixBrand?: boolean;
}

export function seoFromPage(input: SeoFromPageInput): SeoMeta {
  const description = input.description?.trim() || SITE_DEFAULTS.description;
  const ogImage = normalizeImage(input.ogImage) ?? SITE_DEFAULTS.ogImage;
  const suffix = input.suffixBrand ?? !input.title.toLowerCase().includes('memopop');
  const title = suffix ? `${input.title} — ${SITE_DEFAULTS.name}` : input.title;
  return {
    title,
    description,
    canonical: resolveCanonical(input.astro),
    ogType: input.ogType ?? 'website',
    ogImage,
    twitterCard: ogImage ? 'summary_large_image' : 'summary',
    twitterSite: SITE_DEFAULTS.twitterSite,
    twitterCreator: SITE_DEFAULTS.twitterCreator,
    noindex: input.noindex,
  };
}

export interface SeoFromEntryInput {
  astro: AstroLike;
  kind: 'changelog' | 'context-v';
  data: Record<string, unknown>;
  fallbackTitle: string;
}

export function seoFromEntry(input: SeoFromEntryInput): SeoMeta {
  const { data } = input;
  const title = pickStr(data, 'title') ?? input.fallbackTitle;
  const description = pickStr(data, 'lede', 'summary', 'description', 'purpose') ?? SITE_DEFAULTS.description;
  const ogImage =
    normalizeImage(pickStr(data, 'banner_image') ?? null) ??
    normalizeImage(pickStr(data, 'image') ?? null) ??
    SITE_DEFAULTS.ogImage;

  const published = pickDateStr(data, 'date_first_published', 'date_authored_initial_draft', 'date', 'date_created');
  const modified = pickDateStr(data, 'date_modified', 'date_last_updated', 'date_authored_current_draft') ?? published;

  const authorsArr = Array.isArray(data.authors) ? (data.authors as string[]) : [];
  const author = authorsArr[0];
  const tags = Array.isArray(data.tags) ? (data.tags as string[]) : undefined;

  const fullTitle = title.toLowerCase().includes('memopop')
    ? title
    : `${title} — ${input.kind === 'changelog' ? 'Changelog · ' : 'Notes · '}${SITE_DEFAULTS.name}`;

  const jsonLd: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: title,
    description,
    url: resolveCanonical(input.astro),
    image: ogImage?.url,
    datePublished: published,
    dateModified: modified,
    author: authorsArr.length
      ? authorsArr.map((name) => ({ '@type': 'Person', name }))
      : [{ '@type': 'Organization', name: SITE_DEFAULTS.name }],
    publisher: {
      '@type': 'Organization',
      name: 'The Lossless Group',
      url: 'https://www.lossless.group',
    },
    keywords: tags?.join(', '),
  };
  Object.keys(jsonLd).forEach((k) => jsonLd[k] === undefined && delete jsonLd[k]);

  return {
    title: fullTitle,
    description,
    canonical: resolveCanonical(input.astro),
    ogType: 'article',
    ogImage,
    twitterCard: ogImage ? 'summary_large_image' : 'summary',
    twitterSite: SITE_DEFAULTS.twitterSite,
    twitterCreator: SITE_DEFAULTS.twitterCreator,
    publishedTime: published,
    modifiedTime: modified,
    author,
    tags,
    jsonLd,
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────

function pickStr(data: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const k of keys) {
    const v = data[k];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  return undefined;
}

function pickDateStr(data: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const k of keys) {
    const v = data[k];
    if (v instanceof Date && !Number.isNaN(v.getTime())) return v.toISOString();
    if (typeof v === 'string' && v.trim()) {
      const d = new Date(v);
      if (!Number.isNaN(d.getTime())) return d.toISOString();
    }
  }
  return undefined;
}

function normalizeImage(input: OgImage | string | null | undefined): OgImage | undefined {
  if (!input) return undefined;
  if (typeof input === 'string') {
    const url = input.trim();
    if (!url) return undefined;
    return { url };
  }
  if (input.url?.trim()) return input;
  return undefined;
}

/**
 * Picks the best aspect of a content entry's images for an in-page render.
 * Falls back through banner_image → image → square → portrait.
 */
export function pickHeroImage(data: Record<string, unknown>): OgImage | undefined {
  return (
    normalizeImage(pickStr(data, 'banner_image') ?? null) ??
    normalizeImage(pickStr(data, 'image') ?? null) ??
    normalizeImage(pickStr(data, 'square_image') ?? null) ??
    normalizeImage(pickStr(data, 'portrait_image') ?? null)
  );
}
