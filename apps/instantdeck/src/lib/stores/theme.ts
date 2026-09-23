import { browser } from '$app/environment';
import { writable } from 'svelte/store';

export type ThemeMode = 'light' | 'dark';

const STORAGE_KEY = 'deck-aistack-theme';
const defaultTheme: ThemeMode = 'dark';
let initialized = false;

function readStoredTheme(): ThemeMode | null {
  if (!browser) return null;

  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

function createThemeStore() {
  const { subscribe, set, update } = writable<ThemeMode>(defaultTheme);

  function syncDocument(theme: ThemeMode, persist: boolean) {
    if (!browser) return;
    document.documentElement.dataset.theme = theme;
    if (persist) {
      localStorage.setItem(STORAGE_KEY, theme);
    }
  }

  function apply(theme: ThemeMode) {
    syncDocument(theme, true);
    set(theme);
  }

  function init(preferred: ThemeMode = defaultTheme) {
    if (!browser) return;
    const nextTheme = readStoredTheme() ?? preferred;
    syncDocument(nextTheme, false);
    set(nextTheme);
    initialized = true;
  }

  function prime(preferred: ThemeMode = defaultTheme) {
    if (!browser) return;
    if (initialized) return;

    const nextTheme = readStoredTheme() ?? preferred;
    syncDocument(nextTheme, false);
    set(nextTheme);
    initialized = true;
  }

  function toggle() {
    update((current) => {
      const next = current === 'light' ? 'dark' : 'light';
      syncDocument(next, true);
      return next;
    });
  }

  return { subscribe, apply, init, prime, toggle };
}

export const theme = createThemeStore();
