/**
 * Cast manifest loader + per-character live-state derivation.
 *
 * The cast is authored in `characters.md` (frontmatter + prose). This module
 * imports the markdown file's raw text via Vite's `?raw` suffix at build time,
 * splits the YAML frontmatter, and exposes:
 *   - `characters`: typed array of Character entries
 *   - `deriveActiveCharacters(milestones)`: which character ids are currently
 *     active given a stream of milestone events
 *   - `captionFor(characterId, milestones)`: the live caption to display
 *
 * v1 derives state from `MilestoneStage` (the only signal the orchestrator
 * emits today). v2 will add agent-precise captions when milestone events
 * gain an `agent` field; the caption resolver below already prefers
 * agent-matched captions over stage-matched fallbacks, so v2 is a server-only
 * change.
 */

import yaml from 'js-yaml';
import type { MilestoneStage } from '$lib/transport';
import type { Milestone } from '$lib/stores/flow.svelte';

import manifestRaw from './characters.md?raw';

interface AgentCaption {
  id: string;
  caption: string;
}

export interface Character {
  id: string;
  name: string;
  image: string;
  role?: string;
  stages: MilestoneStage[];
  default_caption: string;
  agents: AgentCaption[];
}

interface ManifestFrontmatter {
  title?: string;
  version?: number;
  characters: Character[];
}

function splitFrontmatter(raw: string): { data: unknown; body: string } {
  // Frontmatter is delimited by a leading `---\n` and a closing `\n---\n` (or
  // `\n---\r\n`). Anything before the leading delimiter is rejected — we
  // require the file to open with frontmatter to keep the shape predictable.
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) {
    throw new Error(
      'characters.md is missing or has malformed YAML frontmatter (expected ---\\n...\\n---\\n)'
    );
  }
  const [, yamlBlock, body] = match;
  return { data: yaml.load(yamlBlock), body };
}

const { data } = splitFrontmatter(manifestRaw);
const frontmatter = data as ManifestFrontmatter;

if (!frontmatter || typeof frontmatter !== 'object' || !Array.isArray(frontmatter.characters)) {
  throw new Error('characters.md frontmatter is missing the `characters:` array');
}

export const characters: Character[] = frontmatter.characters.map((c) => ({
  id: c.id,
  name: c.name,
  image: c.image,
  role: c.role,
  stages: c.stages ?? [],
  default_caption: c.default_caption,
  agents: c.agents ?? [],
}));

/**
 * For each character, decide whether it should currently glow.
 *
 * v1 rule:
 *   A character is active when there is at least one milestone whose stage
 *   intersects the character's `stages`, AND no later character has had a
 *   `success`-level milestone fire that would mean we've moved past this
 *   character's territory.
 *
 * Concretely: a character is active when they "own" the most-recently-emitted
 * milestone's stage (or co-own it with another character — multi-glow).
 */
export function deriveActiveCharacters(milestones: Milestone[]): Set<string> {
  const active = new Set<string>();
  if (milestones.length === 0) return active;

  // The "current stage" is the stage of the most recent milestone that is not
  // itself a `complete` lifecycle event. The `complete` stage marks the run's
  // very end and we don't want to claim it for any character — once it fires
  // every character returns to resting.
  let currentStage: MilestoneStage | null = null;
  for (let i = milestones.length - 1; i >= 0; i--) {
    if (milestones[i].stage !== 'complete' && milestones[i].stage !== 'start') {
      currentStage = milestones[i].stage;
      break;
    }
  }
  if (!currentStage) return active;

  for (const ch of characters) {
    if (ch.stages.includes(currentStage)) {
      active.add(ch.id);
    }
  }
  return active;
}

/**
 * The live caption for a character, in priority order:
 *   1. (v2) The most recent milestone whose `agent` matches one of the
 *      character's `agents[].id`. Uses the corresponding `caption`.
 *   2. (v1) The most recent milestone whose `stage` is in `character.stages`.
 *      Uses the milestone's `label` directly.
 *   3. The character's `default_caption`.
 *
 * The v2 step is a no-op today because milestones don't carry `agent` —
 * but it's wired so a server-side patch flips the precision on without a
 * client refactor.
 */
export function captionFor(characterId: string, milestones: Milestone[]): string {
  const ch = characters.find((c) => c.id === characterId);
  if (!ch) return '';

  // Newest-first scan; first hit wins.
  for (let i = milestones.length - 1; i >= 0; i--) {
    const m = milestones[i];
    // v2 path — agent-precise caption.
    const agentId = (m as Milestone & { agent?: string }).agent;
    if (agentId) {
      const tagged = ch.agents.find((a) => a.id === agentId);
      if (tagged) return tagged.caption;
    }
    // v1 path — stage-level fallback.
    if (ch.stages.includes(m.stage)) {
      return m.label;
    }
  }
  return ch.default_caption;
}
