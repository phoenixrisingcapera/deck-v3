import { getContext, setContext, type Snippet } from 'svelte';
import type { HtmlCompiledSlideRenderIdentity, RenderSchema, SmartDeckAssistantRunResponse } from '$lib/api/smartDeckWorkspace';
import type { GlobalDeckSidebarItem } from './GlobalDeckSidebar.svelte';
import type { DeckVisualizerMode } from './GlobalDeckVisualizer.svelte';
import type { SmartDeckUserSlideViewModel } from '$lib/features/smart-deck/user/smartDeckUserTypes';

export type DeckWorkspaceSurface = 'smart-deck' | 'instant-deck' | 'smart-edit' | 'due-diligence';

export type DeckChatMessage = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type DeckVisualizerSlide = {
  title: string;
  slideIndex?: number | null;
  slideNumber?: number | null;
  number?: number | null;
  role?: string | null;
  previewImageUrl?: string | null;
  previewUrl?: string | null;
  thumbnailUrl?: string | null;
};

export interface DeckWorkspaceRegistration {
  surface: DeckWorkspaceSurface;
  sidebar: {
    items: readonly GlobalDeckSidebarItem[];
    activeKey?: string | null;
    ariaLabel?: string;
    onItemChange?: (key: string) => void;
  };
  navigator: {
    slides: SmartDeckUserSlideViewModel[];
    selectedSlideId: string | null;
    selectedSourceSlideIds?: string[];
    onSelectSlide?: (slideId: string) => void;
    onToggleSourceSlideSelection?: (slideId: string) => void;
    onOpenSmartEdit?: (slideId: string) => void;
    onAddSlide?: () => void;
    addingSlide?: boolean;
    title?: string;
    description?: string;
    showSourceSelection?: boolean;
    showSearch?: boolean;
    belowToolbar?: boolean;
    visible?: boolean;
    interactionDisabledReason?: string | null;
  };
  visualizer: {
    title: string;
    subtitle?: string;
    slide?: DeckVisualizerSlide | null;
    renderSchema?: RenderSchema | null;
    htmlSlide?: HtmlCompiledSlideRenderIdentity | null;
    htmlDisplayMode?: 'section' | 'full-document';
    designTokens?: Record<string, string> | null;
    selectedElementId?: string | null;
    lockedElementIds?: string[];
    onSelectElement?: (elementId: string) => void;
    onActivateElement?: (elementId: string) => void;
    onActivateCanvas?: () => void;
    onChangeElementGeometry?: (elementId: string, geometry: { x: number; y: number; width: number; height: number }) => void;
    interactive?: boolean;
    visualMode?: DeckVisualizerMode;
    editable?: boolean;
    emptyTitle?: string;
    emptyText?: string;
    children?: Snippet;
  };
  details?: {
    title?: string;
    slideId?: string | null;
    cacheKey?: string | null;
    persistedSummary?: string | null;
    content?: Snippet;
  };
  chat: {
    messages: DeckChatMessage[];
    state: 'idle' | 'sending' | 'error';
    message?: string;
    onSend: (instruction: string) => void;
    latestAssistantRun?: SmartDeckAssistantRunResponse | null;
    saveInsightState?: 'idle' | 'saving' | 'saved' | 'error';
    saveInsightMessage?: string;
    onSaveInsight?: () => void;
    title?: string;
    eyebrow?: string;
    description?: string;
    emptyText?: string;
    placeholder?: string;
    sendLabel?: string;
    sendingLabel?: string;
    retryAvailable?: boolean;
    onRetry?: () => void;
  };
}

type RegistrationGetter = () => DeckWorkspaceRegistration;
type RegistrationEntry = { token: object; get: RegistrationGetter };

const CONTEXT_KEY = Symbol('deck-workspace-controller');

export function createDeckWorkspaceController() {
  let registration = $state<RegistrationEntry | null>(null);

  return {
    get current() {
      return registration?.get() ?? null;
    },
    register(get: RegistrationGetter) {
      const token = {};
      registration = { token, get };

      return () => {
        if (registration?.token === token) registration = null;
      };
    }
  };
}

export type DeckWorkspaceController = ReturnType<typeof createDeckWorkspaceController>;

export function provideDeckWorkspaceController(controller: DeckWorkspaceController) {
  setContext(CONTEXT_KEY, controller);
}

export function useDeckWorkspaceController() {
  const controller = getContext<DeckWorkspaceController | undefined>(CONTEXT_KEY);
  if (!controller) throw new Error('Deck workspace registration must render inside the deck layout.');
  return controller;
}
