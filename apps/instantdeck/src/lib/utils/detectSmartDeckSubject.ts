import { smartDeckSubjectRegistry } from '$lib/data/smartDeckSubjectRegistry';
import type { SmartDeckSubject, SmartDeckSubjectDetection } from '$lib/types/smart-deck-subjects';

function tokenize(value: string): string[] {
  return value.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

function scoreSubject(subject: (typeof smartDeckSubjectRegistry)[number], haystack: string, tokens: Set<string>): number {
  let score = 0;
  const slug = subject.defaultSlug;

  if (haystack.includes(slug)) score += 6;
  if (haystack.includes(slug.replaceAll('-', ' '))) score += 4;

  for (const variant of subject.slugVariants) {
    if (haystack.includes(variant)) score += 5;
    else if (tokenize(variant).every((token) => tokens.has(token))) score += 3;
  }

  const descriptionTokens = tokenize(subject.description);
  for (const token of descriptionTokens) {
    if (tokens.has(token)) score += 1;
  }

  return score;
}

export function detectSmartDeckSubject(
  title: string | null | undefined,
  extractedText: string | null | undefined,
  existingTags: string[] | null | undefined,
  filename?: string | null,
  context?: string | null
): SmartDeckSubjectDetection {
  const text = [title, extractedText, existingTags?.join(' '), filename, context].filter(Boolean).join(' ').toLowerCase();
  const tokens = new Set(tokenize(text));
  const scored = smartDeckSubjectRegistry
    .map((subject) => ({
      subject,
      score: scoreSubject(subject, text, tokens)
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score);

  const best = scored[0];
  if (!best || best.score < 3) {
    return {
      subject: 'unknown',
      confidence: 0,
      matchedTerms: []
    };
  }

  return {
    subject: best.subject.id as SmartDeckSubject,
    confidence: Math.min(0.98, best.score / 10),
    matchedTerms: [best.subject.defaultSlug, ...best.subject.slugVariants].slice(0, 5)
  };
}
