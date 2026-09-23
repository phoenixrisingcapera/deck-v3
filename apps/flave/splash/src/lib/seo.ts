/**
 * Static SEO copy for the flave splash. Centralized so MetaTags, the index
 * hero, and future OG-image generation all read from one source of truth.
 */

/**
 * OG / share images.
 *
 * None generated yet. When they are, follow `generate-consistent-og-images`
 * and the recipe in `splash/DESIGN.md` §8 (press-room plate stack, empty
 * region upper-left for an SVG title overlay), and ship JPEG rather than
 * WebP per `open-graph-share-seo-geo`.
 *
 * Until then `DEFAULT_OG` is undefined and MetaTags omits the og:image tags
 * entirely — which is correct. A broken or absent image beats a placeholder
 * that unfurls as a grey box.
 */
export const OG_IMAGES = {} as const;

/** The OG image used by default. Undefined until the first round is generated. */
export const DEFAULT_OG = undefined;

export const STATIC_SEO = {
  /** The site-wide brand string appended to per-page titles. */
  brand: 'flave',

  /** Suffix on every page title. */
  titleSuffix: ' — flave',

  siteName: 'flave',

  root: {
    // No leading brand: MetaTags appends titleSuffix (' — flave') unless the
    // title already ends with it, so a brand prefix here doubles it.
    title: 'A document that keeps its workings',
    description:
      'An agent-native document format and editor. Publish a .flave and people see the conclusion; send the file itself and they get the evidence, the data and its sources, and the reasoning that produced it. Built on Lossless Flavored Markdown.',
  },

  changelog: {
    title: 'Changelog',
    description: 'What shipped, when, and why — entry-by-entry notes for flave.',
  },

  contextV: {
    title: 'Context Vigilance',
    description:
      'The spec of record and the thinking around it. Every resolved decision carries its date and its reasoning, including the ones that overturned an earlier position.',
  },
} as const;
