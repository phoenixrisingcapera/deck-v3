/**
 * The fixture corpus.
 *
 * One assertion per trigger. No snapshots — a snapshot suite passes by being
 * regenerated, which is the opposite of a done-condition (Phase 0 plan, and
 * the spec's §1.1 anti-loop rule).
 *
 * Every `expect` is a substring the rendered markup MUST contain. The nesting
 * fixtures are not optional: they are the ones that catch the `toString(node)`
 * bug that lfm's changelog names as the most common reason a freshly-copied
 * Callout "looks fine until an author tries to embed something inside it."
 */
export type Fixture = {
  name: string;
  source: string;
  expect: string[];
  /** Substrings that must NOT appear — usually evidence of a stringified child. */
  reject?: string[];
};

export const FIXTURES: Fixture[] = [
  {
    name: 'heading carries the id lfm computed, never a recomputed one',
    source: '## Metrics that matter',
    expect: ['<h2', 'id="metrics-that-matter"', 'Metrics that matter', '</h2>'],
  },
  {
    name: 'paragraph renders inline marks',
    source: 'Plain **bold** and *em* and `code`.',
    expect: ['<p', '<strong>bold</strong>', '<em>em</em>', '<code>code</code>'],
  },
  {
    name: 'fenced code carries its language',
    source: '```js\nconst a = 1;\n```',
    expect: ['<pre', '<code', 'language-js', 'const a = 1;'],
  },
  {
    name: 'gfm table renders rows and cells',
    source: '| a | b |\n|---|---|\n| 1 | 2 |',
    expect: ['<table', '<thead>', '<tbody>', '<th', '<td', '>1<', '>2<'],
  },
  {
    name: 'unordered list renders items',
    source: '- one\n- two',
    expect: ['<ul', '<li', 'one', 'two'],
  },
  {
    name: 'blockquote renders',
    source: '> just a quote',
    expect: ['<blockquote', 'just a quote'],
  },
  {
    name: 'links and images render with their attributes',
    source: '[text](https://a.b) and ![alt](/img.png)',
    expect: ['<a href="https://a.b"', '>text</a>', '<img', 'src="/img.png"', 'alt="alt"'],
  },
  {
    name: 'callout renders lfm class and title',
    source: '> [!warning] Heads up\n> Body text here.',
    expect: ['callout callout-warning', 'Heads up', 'Body text here.'],
  },

  // ── Nesting. These are the load-bearing fixtures. ────────────────────────
  {
    name: 'NESTING: a table inside a callout renders as a table, not as text',
    source: '> [!warning] Heads up\n>\n> | a | b |\n> |---|---|\n> | 1 | 2 |',
    expect: ['callout callout-warning', '<table', '<td', '>1<'],
    reject: ['[object Object]'],
  },
  {
    name: 'NESTING: a fenced block inside a callout keeps its language',
    source: '> [!note] Code\n>\n> ```js\n> const a = 1;\n> ```',
    expect: ['callout callout-note', '<pre', 'language-js', 'const a = 1;'],
    reject: ['[object Object]'],
  },
  {
    name: 'NESTING: a callout inside a callout renders both',
    source: '> [!note] Outer\n> > [!tip] Inner\n> > deep body',
    expect: ['callout callout-note', 'callout callout-tip', 'deep body'],
    reject: ['[object Object]'],
  },

  // ── Source mapping (D-23). ───────────────────────────────────────────────
  {
    name: 'MAPPING: prose nodes carry source offsets',
    source: '## Metrics that matter\n\nA paragraph.',
    expect: ['data-src-start=', 'data-src-end='],
  },
];
