/**
 * Static SEO + OG defaults for the context-vigilance splash.
 * Per the narrative brief: lead with the marketing-flare quote on the OG card.
 */

export const STATIC_SEO = {
  siteName: 'A neurotic model of Human + AI Product Development.',
  titleSuffix: ' · Context Vigilance',
  root: {
    title: 'Context Vigilance',
    description:
      'Treat context with the same vigilance as code — versioned, reviewed, cross-linked. ' +
      'A live catalog of 1,000+ context-v files across 40 projects, plus the open spec, schema, and kit.',
  },
  corpus: {
    title: 'Corpus — Context Vigilance',
    description:
      'Browse 1,000+ context-v files from 40 Lossless Group projects: specs, plans, prompts, ' +
      'blueprints, reminders, agent-skills, explorations, issues. The proof that the practice is real.',
  },
  search: {
    title: 'Search — Context Vigilance',
    description: 'Full-text search across the corpus.',
  },
} as const;

/**
 * OG card variants generated via Ideogram and hosted on ImageKit. We keep four
 * aspect ratios on hand so per-page MetaTags can pick the one a given platform
 * previews best:
 *
 *   - banner    (16:9, 1200×630)  — Twitter/X "summary_large_image" sweet spot
 *   - portrait  (2:3,  1024×1536) — full-bleed mobile share previews
 *   - square    (1:1,  1024×1024) — LinkedIn / fallback
 *   - preferred (4:5,  1024×1280) — taller frame; renders biggest in iMessage
 *                                    and WhatsApp share-card previews. Default.
 *
 * Width/height values reflect the canonical Ideogram outputs at these aspects;
 * if a future regen lands at a different resolution, update both here and the
 * referenced asset URLs.
 */
export const OG_IMAGES = {
  banner: {
    url: 'https://ik.imagekit.io/xvpgfijuw/Image-Gin/2026-05/Context-Vigilance_content_1778228638490_kLfasPzC6.webp',
    width: 1200,
    height: 630,
    type: 'image/webp',
    alt: 'Context Vigilance — treat context with the same vigilance as code.',
  },
  portrait: {
    url: 'https://ik.imagekit.io/xvpgfijuw/Image-Gin/2026-05/Context-Vigilance_content_1778228639396_WetbQXBAD.webp',
    width: 1024,
    height: 1536,
    type: 'image/webp',
    alt: 'Context Vigilance — treat context with the same vigilance as code.',
  },
  square: {
    url: 'https://ik.imagekit.io/xvpgfijuw/Image-Gin/2026-05/Context-Vigilance_content_1778228639707_ZpucZMAFC.webp',
    width: 1024,
    height: 1024,
    type: 'image/webp',
    alt: 'Context Vigilance — treat context with the same vigilance as code.',
  },
  preferred: {
    url: 'https://ik.imagekit.io/xvpgfijuw/Image-Gin/2026-05/Context-Vigilance_content_1778228640033_hkXIJ6TkP.webp',
    width: 1024,
    height: 1280,
    type: 'image/webp',
    alt: 'Context Vigilance — treat context with the same vigilance as code.',
  },
} as const;

/** Default OG card — the 1024×1536 portrait variant. Tallest of the four
 *  options, so it renders most prominently in iMessage and WhatsApp previews
 *  where most of our shares actually land. Pages can override by passing a
 *  different OG_IMAGES variant to <MetaTags ogImage={...} />. */
export const DEFAULT_OG = OG_IMAGES.portrait;
