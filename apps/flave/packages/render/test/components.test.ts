import { describe, it, expect } from 'vitest';
import { renderLfm } from './helpers';

/**
 * Callout and Table as real components.
 *
 * Written after a human opened the app and reported that a `[!warning]` and a
 * `[!note]` were indistinguishable — which they were, because the renderer
 * dispatched them correctly and the CSS that was supposed to style them was
 * silently discarded by the browser. Markup assertions alone could not see it.
 *
 * These tests assert the HOOKS a stylesheet needs: a stable tone attribute, the
 * raw type preserved, and a marker element. They cannot assert that it LOOKS
 * right — that stays a human rung.
 */
describe('Callout — per-type treatment', () => {
  it('exposes the tone and the raw type as attributes', async () => {
    const html = await renderLfm('> [!warning] Heads up\n> body');
    expect(html).toContain('data-callout-tone="warning"');
    expect(html).toContain('data-callout-type="warning"');
  });

  it('distinguishes note from warning — the reported bug', async () => {
    const warn = await renderLfm('> [!warning] W\n> body');
    const note = await renderLfm('> [!note] N\n> body');
    expect(warn).toContain('data-callout-tone="warning"');
    expect(note).toContain('data-callout-tone="info"');
    expect(warn).not.toContain('data-callout-tone="info"');
  });

  it('maps danger-ish types onto the danger tone', async () => {
    for (const t of ['danger', 'error', 'bug', 'failure']) {
      const html = await renderLfm(`> [!${t}] X\n> body`);
      expect(html, `${t} should be danger`).toContain('data-callout-tone="danger"');
    }
  });

  it('falls back to a neutral tone for an unknown type without dropping it', async () => {
    // lfm accepts any [A-Za-z0-9_-]+ as a callout type, so the vocabulary is
    // open. An unknown type must degrade, never disappear.
    const html = await renderLfm('> [!spaceship-status] Custom\n> body');
    expect(html).toContain('data-callout-tone="neutral"');
    expect(html).toContain('data-callout-type="spaceship-status"');
    expect(html).toContain('Custom');
  });

  it('renders a marker element so the tone is visible without colour alone', async () => {
    const html = await renderLfm('> [!warning] Heads up\n> body');
    expect(html).toContain('callout__marker');
  });

  it('still renders when a callout has no title', async () => {
    const html = await renderLfm('> [!note]\n> just body');
    expect(html).toContain('data-callout-tone="info"');
    expect(html).toContain('just body');
  });
});

describe('Table — a real component', () => {
  it('marks itself as a flave table', async () => {
    const html = await renderLfm('| a | b |\n|---|---|\n| 1 | 2 |');
    expect(html).toContain('<table class="flave-table');
  });

  it('carries column alignment onto cells', async () => {
    const html = await renderLfm('| L | C | R |\n|:---|:---:|---:|\n| 1 | 2 | 3 |');
    expect(html).toContain('data-align="left"');
    expect(html).toContain('data-align="center"');
    expect(html).toContain('data-align="right"');
  });

  it('nests inside a callout with both intact — the reported case', async () => {
    const html = await renderLfm('> [!warning] Heads up\n>\n> | a | b |\n> |---|---|\n> | 1 | 2 |');
    expect(html).toContain('data-callout-tone="warning"');
    expect(html).toContain('<table class="flave-table');
    expect(html).toContain('<td');
    expect(html).not.toContain('[object Object]');
  });
});
