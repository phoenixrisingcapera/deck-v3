/**
 * Static SEO copy for the id-didi-sh splash. Centralized so MetaTags + index
 * hero read from one source of truth.
 */

export const STATIC_SEO = {
  brand: 'didi.sh',
  titleSuffix: ' — didi.sh',
  siteName: 'didi.sh',

  root: {
    title: 'didi.sh — one login to fast-track DD-ready materials',
    description:
      'One didi.sh ID opens three services for venture work: memos that cite their sources (MemoPop), decks that hold up in the data room (DidiDecks), and augment-it, the research corpus that grounds them. Invite-only, no passwords, signed once — valid everywhere.',
  },

  changelog: {
    title: 'Build Log',
    description:
      'The didi.sh identity service, stamped as it ships — every increment on the record.',
  },

  contextV: {
    title: 'Behind the Build',
    description:
      'Implementation-local docs for the didi.sh identity service. The spec of record lives in the ai-labs parent.',
  },
} as const;

/**
 * Default OG image lives in /public/.
 */
export const DEFAULT_OG = {
  url: 'og-banner.png',
  width: 1200,
  height: 630,
  type: 'image/png',
  alt: 'didi.sh — one login to fast-track DD-ready materials',
} as const;
