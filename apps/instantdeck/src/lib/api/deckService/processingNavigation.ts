import type { SmartDeckProcessingStatusWithDiagnostics } from './workflow.client';

export type ReadyProcessingNavigation = {
  instantMode: boolean;
  href: string;
  cancelled: () => boolean;
  beforeNavigate: () => void;
  navigationFailed: () => void;
  navigate: (href: string, options: { invalidateAll: false }) => Promise<unknown>;
};

export async function navigateReadyProcessingWorkspace(
  status: SmartDeckProcessingStatusWithDiagnostics | null,
  context: ReadyProcessingNavigation
): Promise<boolean> {
  if (!status || context.cancelled()) return false;
  if (status.blockingReason === 'backend_unavailable' || (status.backendStatus ?? 0) >= 500) return false;
  const canOpenRequestedWorkspace = context.instantMode ? status.canOpenInstantDeck : status.canOpenSmartDeck;
  if (!canOpenRequestedWorkspace) return false;
  context.beforeNavigate();
  try {
    await context.navigate(context.href, { invalidateAll: false });
  } catch (error) {
    context.navigationFailed();
    throw error;
  }
  return true;
}
