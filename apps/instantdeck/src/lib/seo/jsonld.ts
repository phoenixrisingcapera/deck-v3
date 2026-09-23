import { SITE } from './seo';

export type BreadcrumbJsonLdItem = {
  name: string;
  item: string;
};

export function breadcrumbJsonLd(items: BreadcrumbJsonLdItem[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: `${SITE.url}${item.item}`
    }))
  };
}

export function organizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'deck.aistack.codes',
    url: SITE.url,
    logo: `${SITE.url}/logo.svg`
  };
}

export function softwareApplicationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'deck.aistack.codes',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description:
      'AI-assisted pitch deck redesign platform for founders, consultants, and startup teams.',
    url: SITE.url
  };
}
