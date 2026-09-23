/**
 * Callout tone resolution.
 *
 * lfm accepts ANY `[A-Za-z0-9_-]+` as a callout type, so the vocabulary is
 * open by design — `> [!spaceship-status]` is valid input. A closed switch
 * would silently swallow types nobody anticipated, which is exactly the
 * extensibility flave exists to protect.
 *
 * So this maps the types people actually write onto four tones, and everything
 * else degrades to `neutral` while keeping its raw type on the element. The
 * type is never dropped; only its colour is defaulted.
 */
export type Tone = 'neutral' | 'info' | 'warning' | 'danger';

const TONES: Record<string, Tone> = {
  // info
  note: 'info', info: 'info', tip: 'info', hint: 'info', important: 'info',
  abstract: 'info', summary: 'info', tldr: 'info', example: 'info',
  question: 'info', help: 'info', faq: 'info', quote: 'info', cite: 'info',
  success: 'info', check: 'info', done: 'info', todo: 'info',
  // warning
  warning: 'warning', caution: 'warning', attention: 'warning',
  // danger
  danger: 'danger', error: 'danger', bug: 'danger',
  failure: 'danger', fail: 'danger', missing: 'danger',
};

export function toneFor(type: string | undefined): Tone {
  if (!type) return 'neutral';
  return TONES[type.trim().toLowerCase()] ?? 'neutral';
}
