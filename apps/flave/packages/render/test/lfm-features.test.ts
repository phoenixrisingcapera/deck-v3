import { describe, it, expect } from 'vitest';
import { renderLfm } from './helpers';

/**
 * Features lfm enables by default that the renderer was silently dropping until
 * 2026-08-21. Each of these rendered as *something* before — which is why none
 * of the existing 29 assertions caught them. Wrong-but-plausible output is the
 * failure mode a demo document exposes and a unit test does not.
 */
describe('hProperties passthrough', () => {
  it('carries lfm-computed classes onto the element', async () => {
    const html = await renderLfm('$$ Ops\n## Filing\n&& Two passes');
    expect(html).toContain('heading-block-eyebrow');
    expect(html).toContain('heading-block-subheading');
  });

  it('renders a heading block as an hgroup, not three loose blocks', async () => {
    const html = await renderLfm('$$ Ops\n## Filing\n&& Two passes');
    expect(html).toContain('<hgroup');
    expect(html).toContain('class="heading-block"');
    expect(html).toContain('Ops');
    expect(html).toContain('Filing');
    expect(html).toContain('Two passes');
  });
});

describe('citations', () => {
  it('renders an inline marker instead of dropping the reference', async () => {
    const src = 'A claim.[^a1b2c3]\n\n[^a1b2c3]: [Chroma docs](https://docs.trychroma.com/limits)';
    const html = await renderLfm(src);
    expect(html).toContain('class="citation');
    expect(html).toContain('#cite-a1b2c3');
  });

  it('renders a Sources bibliography from the data bag', async () => {
    const src = 'A claim.[^a1b2c3]\n\n[^a1b2c3]: [Chroma docs](https://docs.trychroma.com/limits)';
    const html = await renderLfm(src);
    expect(html).toContain('Sources');
    expect(html).toContain('https://docs.trychroma.com/limits');
    expect(html).toContain('id="cite-a1b2c3"');
    expect(html).toContain('docs.trychroma.com');
  });

  it('leaves an orphan reference as literal text — remark-gfm never makes it a node', async () => {
    // Measured 2026-08-21: remark-gfm only creates a footnoteReference when a
    // matching definition exists. An orphan stays literal text, so the claim's
    // marker is visible to the author rather than silently disappearing.
    // Citation.svelte's unresolved branch is therefore defensive only — it
    // fires if lfm's citation map ever disagrees with the tree.
    const html = await renderLfm('A claim.[^missing]');
    expect(html).toContain('[^missing]');
    expect(html).not.toContain('class="citation ');
  });

  it('emits no Sources section when there are no citations', async () => {
    const html = await renderLfm('Just a paragraph.');
    expect(html).not.toContain('Sources');
  });
});

describe('gfm', () => {
  it('renders task list checkboxes with their state', async () => {
    const html = await renderLfm('- [x] done\n- [ ] not done');
    expect(html).toContain('data-checked="true"');
    expect(html).toContain('data-checked="false"');
    expect(html).toContain('type="checkbox"');
  });

  it('renders strikethrough', async () => {
    const html = await renderLfm('a ~~struck~~ word');
    expect(html).toContain('<del>struck</del>');
  });

  it('renders nested and ordered lists', async () => {
    const nested = await renderLfm('- one\n  - deep\n- two');
    expect(nested).toContain('deep');
    const ordered = await renderLfm('1. first\n2. second');
    expect(ordered).toContain('<ol');
  });

  it('renders a thematic break', async () => {
    const html = await renderLfm('a\n\n---\n\nb');
    expect(html).toContain('<hr');
  });
});
