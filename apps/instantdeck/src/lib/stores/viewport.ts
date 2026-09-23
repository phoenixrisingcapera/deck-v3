import { browser } from '$app/environment';
import { derived, readable } from 'svelte/store';

type ViewportState = {
  width: number;
  isMobile: boolean;
  isLaptopUp: boolean;
};

const MOBILE_MAX = 768;

export const viewport = readable<ViewportState>(
  { width: 0, isMobile: false, isLaptopUp: true },
  (set) => {
    if (!browser) return () => {};

    const sync = () => {
      const width = window.innerWidth;
      set({
        width,
        isMobile: width <= MOBILE_MAX,
        isLaptopUp: width >= MOBILE_MAX + 1
      });
    };

    sync();
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  }
);

export const isMobileViewport = derived(viewport, ($viewport) => $viewport.isMobile);
