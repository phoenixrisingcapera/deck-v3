export type InstantDeckRecoveryMountInput = {
  requiredReadiness: 'smart_deck' | 'instant_deck';
  requiredWorkspaceReady: boolean;
  sourceWorkspaceReady: boolean;
};

/**
 * Allow the dedicated Instant surface to mount without claiming a generated
 * version is ready. Source processing readiness is the boundary: once the
 * canonical source workspace is available, the customer must be able to open
 * Instant Deck and start the first whole-deck generation. Requiring a failed
 * or existing Instant operation here creates an impossible first-run loop.
 */
export function canMountInstantDeckRecovery(input: InstantDeckRecoveryMountInput): boolean {
  if (input.requiredWorkspaceReady) return true;
  return (
    input.requiredReadiness === 'instant_deck' &&
    input.sourceWorkspaceReady
  );
}
