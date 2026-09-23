import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { renderLfm } from './helpers';
import MetricCard from '../../../apps/editor/src/MetricCard.svelte';
import Badge from '../../../apps/editor/src/Badge.svelte';

/**
 * The demo document is also a fixture.
 *
 * `workspace/content/welcome.md` is what a person sees on first launch, so a
 * feature that silently stops rendering is a first-impression bug. Asserting
 * against the real file — rather than a copy — means the demo cannot drift away
 * from what the renderer actually supports.
 */
const DEMO = fileURLToPath(new URL('../../../workspace/content/welcome.md', import.meta.url));
const packs = { 'metric-card': MetricCard, badge: Badge };

describe('the demo document renders every feature it claims', () => {
  const source = readFileSync(DEMO, 'utf8');

  const FEATURES: Array<[string, string]> = [
    ['heading block (hgroup)', '<hgroup'],
    ['eyebrow class from hProperties', 'heading-block-eyebrow'],
    ['subheading class from hProperties', 'heading-block-subheading'],
    ['heading id from lfm', 'id="1-inline"'],
    ['bold', '<strong>'],
    ['emphasis', '<em>'],
    ['inline code', '<code>'],
    ['strikethrough', '<del>'],
    ['link', '<a href="https://lossless.group"'],
    ['leaf-directive trigger-pack', 'class="badge'],
    ['container trigger-pack', 'class="metric-card'],
    ['unregistered directive degrades to content', 'this prose survives'],
    ['callout info tone', 'data-callout-tone="info"'],
    ['callout warning tone', 'data-callout-tone="warning"'],
    ['callout danger tone', 'data-callout-tone="danger"'],
    ['unknown callout type keeps its type', 'data-callout-type="spaceship-status"'],
    ['unknown callout type falls back to neutral', 'data-callout-tone="neutral"'],
    ['table component', '<table class="flave-table'],
    ['table centre alignment', 'data-align="center"'],
    ['table right alignment', 'data-align="right"'],
    ['task list checked', 'data-checked="true"'],
    ['task list unchecked', 'data-checked="false"'],
    ['ordered list', '<ol'],
    ['fenced code with language', 'language-css'],
    ['plain blockquote', '<blockquote'],
    ['thematic break', '<hr'],
    ['citation marker', 'class="citation'],
    ['sources bibliography', 'id="cite-a1b2c3"'],
  ];

  for (const [name, needle] of FEATURES) {
    it(name, async () => {
      const html = await renderLfm(source, packs);
      expect(html, `demo lost: ${name}`).toContain(needle);
    });
  }

  it('never stringifies a child', async () => {
    const html = await renderLfm(source, packs);
    expect(html).not.toContain('[object Object]');
  });

  it('nests a table inside a callout', async () => {
    const html = await renderLfm(source, packs);
    // Anchor on the callout that actually contains the table — the first
    // 'warning' callout in the demo is the tone example and has none.
    const start = html.indexOf('A table inside a callout');
    expect(start, 'demo lost the nesting section').toBeGreaterThan(-1);
    expect(html.slice(start, start + 2500)).toContain('<table class="flave-table');
  });
});
