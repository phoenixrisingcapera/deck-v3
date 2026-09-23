import { render } from 'svelte/server';
import { parseMarkdown } from '@lossless-group/lfm';
import type { Component } from 'svelte';
import FlaveMarkdown from '../src/FlaveMarkdown.svelte';

/**
 * Svelte 5 interleaves hydration markers — `<!--[-->`, `<!--]-->`, `<!--[0-->`,
 * `<!--[-1-->` — between elements in server output. They are an implementation
 * detail of hydration, not part of the rendered document, and they sit exactly
 * where an assertion like `<td>1</td>` needs to span.
 *
 * Stripping them keeps the fixture assertions readable as markup instead of as
 * marker-tolerant regexes. Real HTML comments authored in an `html` node are
 * untouched: the pattern only matches the `[`/`]`-plus-optional-index shape
 * Svelte emits.
 */
const HYDRATION_MARKER = /<!--[[\]]-?\d*-->/g;

export function stripHydrationMarkers(html: string): string {
  return html.replace(HYDRATION_MARKER, '');
}

/**
 * Parse LFM source and render it through FlaveMarkdown to an HTML string.
 *
 * Server-rendered on purpose: the fixture suite asserts on markup substrings,
 * and a DOM would add cost without adding proof.
 */
export async function renderLfm(
  source: string,
  packs: Record<string, Component<any>> = {},
): Promise<string> {
  const tree = await parseMarkdown(source);
  const { body } = render(FlaveMarkdown, { props: { node: tree, packs } });
  return stripHydrationMarkers(body);
}
