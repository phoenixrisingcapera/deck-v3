import type { SmartDeckDeckType, SmartDeckSubject } from '$lib/types/smart-deck-subjects';
import type { SmartDeckEditorMode, SmartDeckInspectorTab } from './smartDeckUserTypes';

export const SMART_DECK_APP_RAIL_ITEMS = [
  { key: 'slides', icon: '▣', label: 'Slides' },
  { key: 'deck_map', icon: '◫', label: 'Deck Map' },
  { key: 'research', icon: 'R', label: 'Research' },
  { key: 'design', icon: '◈', label: 'Design' },
  { key: 'ai_tools', icon: 'AI', label: 'AI Tools' },
  { key: 'brand', icon: 'B', label: 'Brand' },
  { key: 'data', icon: '◫', label: 'Data' },
  // PRESERVED FOR LEGACY RECLASSIFICATION: Elements/Text/Media were built with
  // product intent, but Smart Edit now owns direct element/design/media
  // manipulation. Keep them visible in source without letting them lead the
  // canonical Smart Deck product order.
  { key: 'elements', icon: '◌', label: 'Elements' },
  { key: 'text', icon: 'T', label: 'Text' },
  { key: 'media', icon: '▧', label: 'Media' },
  // DISABLED: Smart Edit and Due Diligence are canonical shared surface tabs.
  // Repeating them in the Smart Deck rail created duplicate navigation.
  // { key: 'smart_edit', icon: '✎', label: 'Smart Edit' },
  // { key: 'due_diligence', icon: '◉', label: 'Due Diligence' },
  { key: 'settings', icon: '⚙', label: 'Settings' }
] as const;

export const SMART_DECK_EDITOR_MODES: SmartDeckEditorMode[] = ['play', 'edit', 'preview'];
// PRESERVED COMPATIBILITY: market_research remains a recognized inspector ID
// for older persisted state, but the visible Research tool now lives in the rail.
export const SMART_DECK_INSPECTOR_TABS: SmartDeckInspectorTab[] = ['design', 'map', 'market_research', 'ask_ai'];

export const SMART_DECK_QUICK_ACTIONS: Array<{
  label: string;
  prompt: string;
  goal: SmartDeckSubject;
}> = [
  {
    label: 'Improve narrative',
    prompt: 'Improve the narrative flow of this slide and make the story easier for investors to scan.',
    goal: 'problem'
  },
  {
    label: 'Make it more visual',
    prompt: 'Create a stronger visual hierarchy and replace dense copy with cleaner slide design.',
    goal: 'solution'
  },
  {
    label: 'Shorten text',
    prompt: 'Shorten the copy, tighten the message, and make the slide feel presentation-ready.',
    goal: 'traction'
  },
  {
    label: 'Investor-ready version',
    prompt: 'Create an investor-ready version with sharper messaging and a premium venture-style layout.',
    goal: 'ask'
  }
];

export const SMART_DECK_AUDIENCE_OPTIONS = [
  'Investment Committee',
  'VC Partners',
  'Seed Investors',
  'Board Review',
  'Strategic Partners'
];

export const SMART_DECK_DECK_TYPE_OPTIONS: Array<{ value: SmartDeckDeckType; label: string }> = [
  { value: 'startup_pitch', label: 'Startup pitch' },
  { value: 'vc_fund_pitch', label: 'VC fund pitch' },
  { value: 'unknown', label: 'General deck' }
];

export const SMART_DECK_GOAL_OPTIONS: Array<{ value: SmartDeckSubject; label: string }> = [
  { value: 'problem', label: 'Clarify the problem' },
  { value: 'solution', label: 'Sharpen the solution' },
  { value: 'traction', label: 'Highlight traction' },
  { value: 'market_size', label: 'Strengthen market story' },
  { value: 'ask', label: 'Investor-ready ask' },
  { value: 'unknown', label: 'General improvement' }
];
