import type { DesignVersion, GeneratedSlidePreviewStatus, GeneratedSlideSchemaStatus, HtmlCompiledSlideRenderIdentity, RenderSchema, SmartDeckWorkspacePayload } from '$lib/api/smartDeckWorkspace';
import type { SmartDeckDeckType, SmartDeckSubject } from '$lib/types/smart-deck-subjects';

export type SmartDeckEditorMode = 'play' | 'edit' | 'preview';
export type SmartDeckInspectorTab = 'design' | 'map' | 'market_research' | 'ask_ai';
export type SmartDeckDesignTaskType = 'background' | 'style' | 'graph' | 'layout' | 'typography' | 'image';
export type SmartDeckUserSaveState = 'saved' | 'saving' | 'unsaved';
export type SmartDeckAIGenerationState = 'idle' | 'generating' | 'success' | 'error';

export interface SmartDeckUserSlideViewModel {
  id: string;
  number: number;
  title: string;
  thumbnailUrl: string | null;
  previewUrl: string | null;
  sourceThumbnailUrl: string | null;
  sourceSlideId: string | null;
  generatedSlideId: string | null;
  previewStatus: GeneratedSlidePreviewStatus | 'source_only';
  schemaStatus: GeneratedSlideSchemaStatus | 'source_only';
  sourceText: string;
  generatedTitle: string | null;
  hasGeneratedVersion: boolean;
  persistedElements: Array<{
    id: string;
    elementKey: string;
    elementType: string;
    zIndex: number;
    x: number;
    y: number;
    width: number;
    height: number;
    locked: boolean;
    visible: boolean;
    content: Record<string, unknown> | null;
  }>;
  renderMode?: 'scene_graph.v1' | 'html_compiled.v1';
  sectionId?: string | null;
  sourceSlideIds?: string[];
  renderProofStatus?: 'pending' | 'ready' | 'failed';
  designVersionId: string | null;
  htmlArtifactId: string | null;
  htmlSlide: HtmlCompiledSlideRenderIdentity | null;
}

export interface SmartDeckUserVersionViewModel {
  id: string;
  label: string;
  name: string;
  status: string;
  isActive: boolean;
  createdAt: string;
  slideCount: number;
  designVersion: DesignVersion;
}

export interface SmartDeckUserViewModel {
  deckId: string;
  deckName: string;
  audience: string | null;
  purpose: string | null;
  slides: SmartDeckUserSlideViewModel[];
  selectedSlide: SmartDeckUserSlideViewModel | null;
  generatedVersions: SmartDeckUserVersionViewModel[];
  selectedVersion: SmartDeckUserVersionViewModel | null;
  workspaceStatus: SmartDeckWorkspacePayload['generatedWorkspaceStatus'] | null;
  coverageComplete: boolean;
  deckMapContext: {
    slides: Array<{
      slideId: string;
      slideNumber: number;
      title: string;
      role: string | null;
      extractedText: string;
      thumbnailUrl: string | null;
      previewImageUrl: string | null;
      hasGeneratedVersion: boolean;
      generatedSlideId: string | null;
      persistedElements: Array<{
        id: string;
        elementKey: string;
        elementType: string;
        semanticLabel: string;
        locked: boolean;
        visible: boolean;
        targetCapabilities: {
          smartEdit: boolean;
          design: boolean;
        };
        isSelected: boolean;
        rawType: string;
        exactContent: string;
        generatedSlideId: string | null;
        slideId: string;
        x: number;
        y: number;
        width: number;
        height: number;
        zIndex: number;
        contentPreview: string;
      }>;
    }>;
    readyForLlm: boolean;
  };
}

export interface SmartDeckUserAiContext {
  audience: string | null;
  deckType: SmartDeckDeckType;
  goal: SmartDeckSubject;
  prompt: string;
}

export interface SmartDeckCanvasState {
  renderSchema: RenderSchema | null;
  designTokens: Record<string, string> | null;
  validationStatus: string | null;
  selectedElementId: string | null;
}

export interface SmartDeckUserGenerationResult {
  generationJobId: string;
  workspace: SmartDeckWorkspacePayload;
  designVersion: DesignVersion | null;
}
