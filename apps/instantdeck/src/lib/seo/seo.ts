export type SeoConfig = {
  title: string;
  description: string;
  canonicalPath: string;
  image?: string;
  type?: 'website' | 'article';
  noindex?: boolean;
  changeFrequency?: 'daily' | 'weekly' | 'monthly' | 'yearly';
  priority?: number;
  publishedTime?: string;
  modifiedTime?: string;
  keywords?: string[];
};

export const SITE = {
  name: 'deck.aistack.codes',
  url: 'https://deck.aistack.codes',
  defaultImage: 'https://deck.aistack.codes/logo.png',
  twitterHandle: 'deck.aistack.codes'
} as const;

export function buildTitle(title: string) {
  if (title.includes('Deck AIStack') || title.includes('deck.aistack.codes')) return title;
  return `${title} | deck.aistack.codes`;
}

export function normalizePath(path: string) {
  if (!path || path === '/') return '/';
  const withLeadingSlash = path.startsWith('/') ? path : `/${path}`;
  return withLeadingSlash.length > 1 ? withLeadingSlash.replace(/\/+$/, '') : withLeadingSlash;
}

export function canonicalUrl(path: string) {
  return `${SITE.url}${normalizePath(path)}`;
}
