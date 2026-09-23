import { describe, it, expect } from 'vitest';
import { render } from 'svelte/server';
import Smoke from './Smoke.svelte';

// Toolchain proof, not a product test. If this fails, nothing below it is
// meaningful — the spec's own warning is that "toolchain trouble generates more
// loops than logic ever does," so this rung gets climbed first.
describe('toolchain', () => {
  it('renders a Svelte 5 component to an HTML string via svelte/server', () => {
    const { body } = render(Smoke, { props: { name: 'flave' } });
    expect(body).toContain('flave');
    expect(body).toContain('class="smoke"');
  });
});
