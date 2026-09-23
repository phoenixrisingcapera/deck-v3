import {
  startSmartDeckGenerationWorkflow,
  waitForWorkflowJobCompletion,
  type DesignVersion,
  type HtmlCompiledSlideRenderIdentity,
  type SmartDeckGenerationInput,
  type SmartDeckWorkspacePayload
} from '$lib/api/smartDeckWorkspace';
import { deckProductApiPath } from '$lib/contracts';
import { fetchApiJsonOrThrow } from '$lib/api/apiError';
import type { SmartDeckUserViewModel } from '$lib/features/smart-deck/user/smartDeckUserTypes';

/**
 * Instant Deck owns a dedicated product read/write contract. Shared type and
 * polling helpers remain transport utilities; no Smart Deck workspace endpoint
 * participates in this page runtime.
 */
export async function getInstantDeckWorkspace(deckId: string, signal?: AbortSignal) {
  return fetchApiJsonOrThrow<SmartDeckWorkspacePayload>(
    deckProductApiPath(`/decks/${deckId}/instant-deck`),
    { signal },
    'Instant Deck workspace lookup failed.'
  );
}

export async function saveInstantDeckSelection(
  deckId: string,
  input: {
    activeSourceSlideId?: string | null;
    activeDesignVersionId?: string | null;
    activeGeneratedSlideId?: string | null;
  }
) {
  return fetchApiJsonOrThrow<SmartDeckWorkspacePayload['preferences']>(
    deckProductApiPath(`/decks/${deckId}/instant-deck/session-state`),
    {
      method: 'PATCH',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input)
    },
    'Instant Deck session state update failed.'
  );
}

export function toHtmlDeckIdentity(
  deckId: string,
  version: DesignVersion | null,
  generatedSlide: DesignVersion['generatedSlides'][number] | null | undefined
): HtmlCompiledSlideRenderIdentity | null {
  const artifact = version?.htmlArtifact;
  if (
    !version ||
    version.renderMode !== 'html_compiled.v1' ||
    !artifact?.id ||
    !artifact.sha256 ||
    !generatedSlide ||
    generatedSlide.renderMode !== 'html_compiled.v1' ||
    !generatedSlide.sectionId
  ) return null;

  return {
    deckId,
    designVersionId: version.id,
    htmlArtifactId: artifact.id,
    artifactSha256: artifact.sha256,
    generatedSlideId: generatedSlide.id,
    sectionId: generatedSlide.sectionId,
    sectionSha256: generatedSlide.sectionSha256 ?? null,
    compilationHash: generatedSlide.compilationHash ?? null,
    renderMode: 'html_compiled.v1',
    renderProofStatus: generatedSlide.renderProofStatus ?? version.renderProofStatus ?? 'pending'
  };
}

export function toInstantDeckSlideRail(
  version: DesignVersion | null,
  sourceSlides: SmartDeckWorkspacePayload['sourceSlides']
): SmartDeckUserViewModel['slides'] {
  if (!version) return [];

  return version.generatedSlides.map((generatedSlide, index) => {
    const sourceSlide = sourceSlides.find((slide) => slide.id === generatedSlide.sourceSlideId) ?? null;
    const number = generatedSlide.slideNumber ?? sourceSlide?.slideNumber ?? index + 1;
    const title = generatedSlide.title?.trim() || sourceSlide?.title?.trim() || `Slide ${String(number).padStart(2, '0')}`;
    const htmlSlide = toHtmlDeckIdentity(version.deckId, version, generatedSlide);
    return {
      id: generatedSlide.id,
      number,
      title,
      thumbnailUrl: null,
      previewUrl: null,
      sourceThumbnailUrl: null,
      sourceSlideId: generatedSlide.sourceSlideId ?? null,
      generatedSlideId: generatedSlide.id,
      previewStatus: generatedSlide.previewStatus ?? 'pending',
      schemaStatus: generatedSlide.schemaStatus ?? 'ready',
      sourceText: sourceSlide?.extractedText ?? '',
      generatedTitle: generatedSlide.title ?? null,
      hasGeneratedVersion: true,
      renderMode: generatedSlide.renderMode ?? 'html_compiled.v1',
      sectionId: generatedSlide.sectionId ?? null,
      sourceSlideIds: generatedSlide.sourceSlideIds ?? (generatedSlide.sourceSlideId ? [generatedSlide.sourceSlideId] : []),
      renderProofStatus: generatedSlide.renderProofStatus ?? 'pending',
      designVersionId: version.id,
      htmlArtifactId: version.htmlArtifact?.id ?? null,
      htmlSlide,
      persistedElements: []
    };
  });
}

export async function generateInstantDeckVersion(
  deckId: string,
  input: SmartDeckGenerationInput,
  signal?: AbortSignal
) {
  const accepted = await startSmartDeckGenerationWorkflow(deckId, {
    ...input,
    generationMode: 'instant_deck',
    outputContract: 'full_html_deck.v1'
  });
  const completed = await waitForWorkflowJobCompletion(
    accepted.jobId,
    'Instant Deck generation failed.',
    undefined,
    undefined,
    undefined,
    signal
  );
  if (completed.status !== 'completed') {
    throw new Error(completed.errorMessage ?? 'Instant Deck generation did not complete.');
  }

  const workspace = completed.workspace ?? await getInstantDeckWorkspace(deckId, signal);
  const designVersion = workspace.designVersions.find((version) =>
    version.generationJobId === accepted.jobId &&
    (!completed.designVersion?.id || version.id === completed.designVersion.id)
  ) ?? null;
  return { generationJobId: accepted.jobId, workspace, designVersion };
}
