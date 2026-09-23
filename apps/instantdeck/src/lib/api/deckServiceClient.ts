/*
  Frontend API client for DeckAiStack.

  This file only bridges UI events to backend routes. It does not own deck
  processing, workflow truth, storage, or billing/session state.

  Product deck APIs should stay under:
    /api/products/deck-aistack-codes/*

  Auth and workspace settings may live on separate backend route families when
  the server exposes them that way, but this client must always surface backend
  failures as structured errors rather than letting the UI spin indefinitely.
*/

import { fetchApiJsonOrThrow, readApiJsonOrThrow } from './apiError';
import { createUploadRequestId } from './uploadRequestIdentity';
import { postUploadWithTransportRetry } from './deckService/uploadTransport';
import { deckProductApiPath } from '$lib/contracts';
import type {
  FirstDeckUploadRouteResponse,
  SaveConfirmation,
  WorkspaceAiProviderRouteResponse,
  WorkspaceAiProviderSaveRequest,
  WorkspaceAiProviderSaveRouteResponse,
  WorkspaceSummary,
  WorkspaceSummaryRouteResponse
} from '$lib/contracts';

type DeckUploadStage = 'creating' | 'requesting_upload' | 'uploading' | 'confirming' | 'processing' | 'ready';

const RAILWAY_PROXY_SAFE_UPLOAD_BYTES = 30 * 1024 * 1024;

// Human-readable upload lifecycle emitted to screens. These values are UI
// progress labels only; the backend workflow-state remains the source of truth
// for whether a deck can open in Smart Deck.

type InspectionResponse = {
  enabled: boolean;
  active: boolean;
  founderEmail: string | null;
  hasPassword: boolean;
  backendConfigured: boolean;
  bypasses: {
    routeAccess: boolean;
    billing: boolean;
    providers: boolean;
  };
};

type SessionValidationResponse = {
  valid: boolean;
  inspection?: InspectionResponse;
};

type SignInRequest = {
  email: string;
  password: string;
};

type SignUpRequest = {
  name: string;
  email: string;
  password: string;
  companyName?: string;
  role?: 'general' | 'user';
  acceptedTerms: boolean;
};

type AuthRouteResponse = {
  nextUrl: string;
  user: {
    id: string;
    email: string;
    name: string;
    role: 'super_admin' | 'admin' | 'user' | 'general';
  };
  workspace?: {
    id: string;
    name: string;
  };
};

type PublicInterestPayload = {
  email: string;
  name?: string;
  company_name?: string;
  company_website_url?: string;
  role_label?: string;
  use_case?: string;
  message?: string;
  source_page?: string;
  turnstileToken?: string;
};

type PublicInterestResponse = {
  ok: true;
  lead_id: string;
  message: string;
};

type CurrentUserResponse = {
  user: {
    id: string;
    email: string;
    name: string;
    role: 'super_admin' | 'admin' | 'user';
    preferredTheme: 'light' | 'dark';
    billingPlan: string;
    permissions: string[];
    
  };
  inspection?: SessionValidationResponse['inspection'];
};

type BillingStateResponse = {
  plan: string;
  status?: string;
};

type DeckUploadIntake = {
  // Optional intake metadata that travels with the source file so backend
  // workers can classify the deck for the intended audience and purpose.
  companyName?: string;
  websiteUrl?: string;
  audience?: string;
  purpose?: string;
  founderName?: string;
  notes?: string;
  teamNotes?: string;
  linkedinUrls?: string[];
  supportingUrls?: string[];
  preferredWorkspace?: 'smart_deck' | 'instant_deck';
};

type DeckUploadCompleteResponse = {
  deckId?: string;
  filename?: string;
  deckExtractionStatus?: FirstDeckUploadRouteResponse['deckExtractionStatus'];
  preferredWorkspace?: 'smart_deck' | 'instant_deck';
  preferredWorkspaceUrl?: string | null;
  queueError?: string | null;
  queueFailureTicketId?: string | null;
  requestId?: string | null;
  failureTicketId?: string | null;
  processing?: Record<string, unknown> | null;
  confirmation?: SaveConfirmation | null;
};

type DeckUploadFlowOptions = {
  onStage?: (stage: DeckUploadStage) => void;
};

function buildUrl(path: string) {
  // Client callers pass either product proxy paths (`/api/...`) or legacy app
  // paths (`/me`). Keep this adapter explicit so route families do not drift.
  if (/^https?:\/\//i.test(path)) {
    throw new Error('deckServiceClient only accepts same-origin API paths.');
  }

  if (path.startsWith('/api/')) {
    return path;
  }

  return `/api${path}`;
}

async function deckServiceApiGet<T>(path: string): Promise<T> {
  // Shared GET wrapper so route-family changes do not leak into the UI and all
  // session-backed calls include cookies.
  return fetchApiJsonOrThrow<T>(buildUrl(path), { credentials: 'include' }, `GET ${path} failed`);
}

async function deckServiceApiPost<T>(path: string, body?: unknown): Promise<T> {
  // Shared POST wrapper for auth/session, billing, and lightweight product
  // actions that use JSON bodies. Multipart uploads intentionally bypass this.
  return fetchApiJsonOrThrow<T>(
    buildUrl(path),
    {
      method: 'POST',
      credentials: 'include',
      headers: body ? { 'content-type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined
    },
    `POST ${path} failed`
  );
}

function compactStringList(values: string[] | undefined): string[] {
  // Normalize user-supplied URL lists before multipart upload so blank entries
  // do not become backend form fields with empty string payloads.
  return (values ?? []).map((value) => value.trim()).filter(Boolean);
}

function readWorkspaceSummary(payload: WorkspaceSummaryRouteResponse): WorkspaceSummary {
  if (!payload?.workspace || typeof payload.workspace !== 'object') {
    throw new Error('Workspace summary did not include a workspace.');
  }

  return payload.workspace;
}

async function uploadDeckViaProductRoute(
  file: File,
  intake?: DeckUploadIntake,
  requestId: string = createUploadRequestId()
): Promise<DeckUploadCompleteResponse> {
  // Multipart upload payload sent to the product route. Keep field names aligned
  // with the backend contract; changing them silently breaks extraction intake.
  const formData = new FormData();
  formData.set('deck', file);
  formData.set('audience', intake?.audience?.trim() || 'Investment Committee');
  formData.set('purpose', intake?.purpose?.trim() || 'Initial diligence review');
  if (intake?.companyName?.trim()) formData.set('company_name', intake.companyName.trim());
  if (intake?.websiteUrl?.trim()) formData.set('website_url', intake.websiteUrl.trim());
  if (intake?.founderName?.trim()) formData.set('founder_name', intake.founderName.trim());
  if (intake?.notes?.trim()) formData.set('notes', intake.notes.trim());
  if (intake?.teamNotes?.trim()) formData.set('team_notes', intake.teamNotes.trim());
  if (intake?.linkedinUrls?.length) {
    const linkedinUrls = compactStringList(intake.linkedinUrls);
    if (linkedinUrls.length > 0) formData.set('linkedin_urls', linkedinUrls.join('\n'));
  }
  if (intake?.supportingUrls?.length) {
    const supportingUrls = compactStringList(intake.supportingUrls);
    if (supportingUrls.length > 0) formData.set('supporting_urls', supportingUrls.join('\n'));
  }
  if (intake?.preferredWorkspace === 'instant_deck') formData.set('preferred_workspace', 'instant_deck');

  const endpointPath = deckProductApiPath('/decks/upload');
  // Milestone-one uploads retry only safe transport failures (connection
  // rejection, request timeout, gateway/unavailable statuses) and always
  // resend the SAME request identity so the backend replay deduplicates.
  // A rejected fetch has an ambiguous server outcome and must never trigger a
  // browser resend to an older instance that may not share the durable
  // coordination table - postUploadWithTransportRetry caps that at the same
  // request id, never as a brand-new upload.
  return postUploadWithTransportRetry<DeckUploadCompleteResponse>({
    requestId,
    endpointPath,
    buildBody: () => formData,
    readResponse: (response) =>
      readApiJsonOrThrow<DeckUploadCompleteResponse>(response, 'Deck upload failed.', endpointPath)
  });
}

async function uploadDeckViaPresignedRoute(
  file: File,
  intake: DeckUploadIntake | undefined,
  options: DeckUploadFlowOptions
): Promise<DeckUploadCompleteResponse> {
  options.onStage?.('creating');
  const createPath = deckProductApiPath('/decks/create');
  const deck = await fetchApiJsonOrThrow<Record<string, unknown>>(
    createPath,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        title: file.name.replace(/\.[^.]+$/, '') || 'Uploaded deck',
        audience: intake?.audience?.trim() || 'Investment Committee',
        purpose: intake?.purpose?.trim() || 'Initial diligence review'
      })
    },
    'Could not create the deck upload record.'
  );
  const deckId = String(deck.id ?? '');
  if (!deckId) throw new Error('Deck creation finished without a persisted deck id.');

  options.onStage?.('requesting_upload');
  const uploadPath = deckProductApiPath(`/decks/${deckId}/upload-url`);
  const prepared = await fetchApiJsonOrThrow<{ upload?: Record<string, unknown> }>(
    uploadPath,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ filename: file.name, mimeType: file.type || 'application/pdf', sizeBytes: file.size })
    },
    'Could not prepare the object-storage upload.'
  );
  const upload = prepared.upload ?? {};
  const uploadUrl = String(upload.uploadUrl ?? '');
  const storagePath = String(upload.storagePath ?? '');
  if (!uploadUrl || !storagePath) throw new Error('Object-storage upload preparation returned an incomplete response.');

  options.onStage?.('uploading');
  const putResponse = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'content-type': file.type || 'application/pdf' },
    body: file
  });
  if (!putResponse.ok) throw new Error(`Object-storage upload failed with status ${putResponse.status}.`);

  options.onStage?.('confirming');
  const completePath = deckProductApiPath(`/decks/${deckId}/upload-complete`);
  const completion = await fetchApiJsonOrThrow<Record<string, unknown>>(
    completePath,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        storagePath,
        filename: file.name,
        mimeType: file.type || 'application/pdf',
        sizeBytes: file.size,
        websiteUrl: intake?.websiteUrl?.trim() || undefined,
        preferredWorkspace: intake?.preferredWorkspace === 'instant_deck' ? 'instant_deck' : 'smart_deck'
      })
    },
    'Could not confirm the object-storage upload.'
  );
  options.onStage?.('ready');
  const processing = completion.processing && typeof completion.processing === 'object'
    ? completion.processing as Record<string, unknown>
    : null;
  const processingStatus = processing?.status;
  const deckExtractionStatus = processingStatus === 'ready' || processingStatus === 'failed' || processingStatus === 'queued' || processingStatus === 'idle' || processingStatus === 'processing'
    ? processingStatus
    : 'queued';
  return {
    ...(completion as DeckUploadCompleteResponse),
    deckId,
    filename: file.name,
    deckExtractionStatus,
    preferredWorkspace: intake?.preferredWorkspace === 'instant_deck' ? 'instant_deck' : 'smart_deck'
  };
}

async function uploadFirstDeckViaBridge(file: File, payload?: unknown, options: DeckUploadFlowOptions = {}): Promise<FirstDeckUploadRouteResponse> {
  // High-level upload flow used by intake screens. It saves the source deck and
  // fetches workspace summary, but it never decides extraction or Smart Deck readiness.
  const intake = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
  const requestId = createUploadRequestId();

  // Keep the UI honest about the upload lifecycle. We only emit processing when the backend actually starts work.
  const normalizedIntake: DeckUploadIntake = {
      companyName: typeof intake.companyName === 'string' ? intake.companyName : undefined,
      websiteUrl: typeof intake.websiteUrl === 'string' ? intake.websiteUrl : undefined,
      audience: typeof intake.audience === 'string' ? intake.audience : undefined,
      purpose: typeof intake.purpose === 'string' ? intake.purpose : undefined,
      founderName: typeof intake.founderName === 'string' ? intake.founderName : undefined,
      notes: typeof intake.notes === 'string' ? intake.notes : undefined,
      teamNotes: typeof intake.teamNotes === 'string' ? intake.teamNotes : undefined,
      linkedinUrls: Array.isArray(intake.linkedinUrls)
        ? intake.linkedinUrls.filter((value): value is string => typeof value === 'string')
        : [],
      supportingUrls: Array.isArray(intake.supportingUrls)
        ? intake.supportingUrls.filter((value): value is string => typeof value === 'string')
        : [],
      preferredWorkspace: intake.preferredWorkspace === 'instant_deck' ? 'instant_deck' : 'smart_deck'
  };
  const confirmation = file.size > RAILWAY_PROXY_SAFE_UPLOAD_BYTES
    ? await uploadDeckViaPresignedRoute(file, normalizedIntake, options)
    : await (async () => {
        options.onStage?.('creating');
        options.onStage?.('requesting_upload');
        options.onStage?.('uploading');
        return uploadDeckViaProductRoute(file, normalizedIntake, requestId);
      })();
  const deckId = String(confirmation.deckId ?? '');
  if (!deckId) {
    // A persisted deck id is required for processing polling and every later
    // Smart Deck route, so missing ids are treated as hard upload failures.
    throw new Error('Deck upload finished without a persisted deck id.');
  }

  options.onStage?.('confirming');
  let workspace: WorkspaceSummary | null = null;
  try {
    const workspaceSummary = await deckServiceApiGet<WorkspaceSummaryRouteResponse>(deckProductApiPath('/workspace-summary'));
    // Workspace summary refresh lets dashboard/upload surfaces update after the
    // source file is saved. It does not prove Smart Deck generation is complete.
    workspace = readWorkspaceSummary(workspaceSummary);
  } catch {
    // Summary refresh is best-effort. A saved deck id must always continue to
    // processing so miniature generation and Smart Deck activation can proceed.
    workspace = null;
  }
  options.onStage?.('ready');
  return {
    ok: true,
    deckId,
    filename: confirmation.filename ?? file.name,
    deckExtractionStatus: confirmation.deckExtractionStatus,
    preferredWorkspace: confirmation.preferredWorkspace ?? 'smart_deck',
    preferredWorkspaceUrl: confirmation.preferredWorkspaceUrl ?? null,
    queueError: confirmation.queueError ?? null,
    queueFailureTicketId: confirmation.queueFailureTicketId ?? null,
    requestId: confirmation.requestId ?? null,
    failureTicketId: confirmation.failureTicketId ?? null,
    processing: confirmation.processing ?? null,
    confirmation: confirmation.confirmation ?? null,
    workspace: workspace ?? {
      workspace: { id: 'pending', name: 'Deck AIStack Workspace' },
      deckCount: 1,
      activeDeckId: deckId,
      latestDecks: [],
      processingDeckCount: 1,
      readyDeckCount: 0,
      exportCount: 0,
      firstTimeTemplates: []
    }
  };
}

async function getWorkspaceAiProviderViaBridge(workspaceId?: string | null): Promise<WorkspaceAiProviderRouteResponse> {
  // AI-provider settings are proxied through SvelteKit because browser code
  // should not know the backend base URL or token format.
  try {
    const query = workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : '';
    const response = await fetch(`/api/settings/workspace/ai-provider${query}`, {
      credentials: 'include'
    });
    return await readApiJsonOrThrow<WorkspaceAiProviderRouteResponse>(
      response,
      'Could not load workspace AI configuration.',
      '/api/settings/workspace/ai-provider'
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('Could not load workspace AI configuration.');
  }
}

async function saveWorkspaceAiProviderViaBridge(
  payload: WorkspaceAiProviderSaveRequest
): Promise<WorkspaceAiProviderSaveRouteResponse> {
  // Persist provider settings with the same structured error handling as load.
  // This keeps provider misconfiguration visible instead of silently falling back.
  try {
    const response = await fetch('/api/settings/workspace/ai-provider', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'content-type': 'application/json'
      },
      body: JSON.stringify(payload)
    });
    return await readApiJsonOrThrow<WorkspaceAiProviderSaveRouteResponse>(
      response,
      'Could not save workspace AI configuration.',
      '/api/settings/workspace/ai-provider'
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('Could not save workspace AI configuration.');
  }
}

async function revokeWorkspaceAiProviderViaBridge(workspaceId?: string | null): Promise<WorkspaceAiProviderRouteResponse & { revoked: boolean }> {
  try {
    const query = workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : '';
    const response = await fetch(`/api/settings/workspace/ai-provider${query}`, {
      method: 'DELETE',
      credentials: 'include'
    });
    return await readApiJsonOrThrow<WorkspaceAiProviderRouteResponse & { revoked: boolean }>(
      response,
      'Could not revoke workspace AI configuration.',
      '/api/settings/workspace/ai-provider'
    );
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('Could not revoke workspace AI configuration.');
  }
}

export const deckServiceClient = {
  // Product workspace/deck calls stay under /api/products/deck-aistack-codes/*.
  getWorkspaceSummary: () => deckServiceApiGet<WorkspaceSummaryRouteResponse>(deckProductApiPath('/workspace-summary')),
  uploadFirstDeck: (file: File, payload?: unknown, options?: DeckUploadFlowOptions): Promise<FirstDeckUploadRouteResponse> =>
    uploadFirstDeckViaBridge(file, payload, options),
  // Workspace provider settings use their own proxy route because they are not
  // deck-specific workflow commands.
  getWorkspaceAiProvider: (workspaceId?: string | null) => getWorkspaceAiProviderViaBridge(workspaceId),
  saveWorkspaceAiProvider: (payload: WorkspaceAiProviderSaveRequest) => saveWorkspaceAiProviderViaBridge(payload),
  revokeWorkspaceAiProvider: (workspaceId?: string | null) => revokeWorkspaceAiProviderViaBridge(workspaceId),
  // Public lead capture is intentionally lightweight and separate from deck auth.
  submitPublicInterest: (payload: PublicInterestPayload) =>
    deckServiceApiPost<PublicInterestResponse>('/public/interest', payload)
};
