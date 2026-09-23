import { describe, it, expect } from 'vitest';
import { parseMarkdown } from '@lossless-group/lfm';
import { renderLfm } from './helpers';
import { FIXTURES } from './fixtures';
import MetricCard from './MetricCard.svelte';

describe('fixture corpus', () => {
  for (const f of FIXTURES) {
    it(f.name, async () => {
      const html = await renderLfm(f.source);
      for (const needle of f.expect) {
        expect(html, `missing ${JSON.stringify(needle)} in:\n${html}`).toContain(needle);
      }
      for (const bad of f.reject ?? []) {
        expect(html, `found forbidden ${JSON.stringify(bad)} in:\n${html}`).not.toContain(bad);
      }
    });
  }
});

describe('trigger-pack registry — the one extensibility branch', () => {
  it('renders a registered component for an unknown directive, with attributes as props', async () => {
    const html = await renderLfm(':::metric-card{value="42" label="ARR"}\n:::', {
      'metric-card': MetricCard,
    });
    expect(html).toContain('class="metric-card"');
    expect(html).toContain('42');
    expect(html).toContain('ARR');
  });

  it('does not crash on an unregistered directive — it still renders the children', async () => {
    const html = await renderLfm(':::not-registered\ninner prose\n:::');
    expect(html).toContain('inner prose');
  });

  it('a leaf directive resolves from the registry too', async () => {
    const html = await renderLfm('::metric-card{value="7" label="NPS"}', {
      'metric-card': MetricCard,
    });
    expect(html).toContain('class="metric-card"');
    expect(html).toContain('7');
  });
});

describe('invariants carried over from lfm', () => {
  it('heading ids come from lfm and are never recomputed by the renderer', async () => {
    // Punctuation and casing are exactly where two slugify implementations drift.
    const source = '### The `flatten` contract — D-01, resolved!';
    const tree = await parseMarkdown(source);
    const heading = (tree.children as any[])[0];
    const lfmId = heading.data?.id;

    expect(lfmId, 'lfm should have stamped an id').toBeTruthy();

    const html = await renderLfm(source);
    expect(html, 'renderer must emit lfm id verbatim').toContain(`id="${lfmId}"`);
  });

  it('containers recurse through the renderer rather than stringifying children', async () => {
    const html = await renderLfm('> [!info] Outer\n>\n> - a list item');
    expect(html).toContain('<li');
    expect(html).not.toContain('[object Object]');
  });
});

describe('D-23 — the source-mapping asymmetry this phase is built on', () => {
  it('prose nodes carry position; lfm-synthesized callouts do not', async () => {
    const tree: any = await parseMarkdown('## A heading\n\n> [!note] Title\n> body');
    const heading = tree.children[0];
    const callout = tree.children[1];

    expect(heading.type).toBe('heading');
    expect(heading.position?.start?.offset, 'prose must be mappable').toBeTypeOf('number');

    expect(callout.type).toBe('containerDirective');
    expect(callout.name).toBe('callout');
    // If this ever fails, lfm started stamping position on synthesized nodes and
    // D-23 should be revisited — that is a decision, not a test to "fix".
    expect(callout.position, 'D-23 premise: synthesized nodes are unmapped').toBeUndefined();
  });

  it('a user-defined directive DOES carry position, unlike a callout', async () => {
    const tree: any = await parseMarkdown(':::metric-card{value="42"}\nbody\n:::');
    const directive = tree.children[0];
    expect(directive.type).toBe('containerDirective');
    expect(directive.name).toBe('metric-card');
    // Measured 2026-08-20: raw remark-directive nodes keep their position. The
    // Phase 0 plan originally lumped trigger-packs in with callouts as
    // "unmapped" — that was wrong. Components are select-not-edit by DESIGN
    // (an inverse serializer per pack is the cost we refuse), not by data.
    expect(directive.position?.start?.offset).toBeTypeOf('number');
  });
});
