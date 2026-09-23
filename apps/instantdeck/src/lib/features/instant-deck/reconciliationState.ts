type PersistedJob = { id?: string; status: string; createdAt: string };
type WorkflowOutcome = {
  status: string;
  authoritativeInstantChain?: { generationJobId: string } | null;
};

/** A completed source upload does not erase a failed generation attempt. */
export function instantDeckReconciliationState(jobs: PersistedJob[], hasVersion: boolean, workflow?: WorkflowOutcome) {
  const latest = [...jobs].sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0];
  const downstreamFailed = Boolean(latest?.id &&
    workflow?.authoritativeInstantChain?.generationJobId === latest.id && workflow.status === 'failed');
  if (latest && (downstreamFailed || ['failed', 'failed_final', 'failed_retryable', 'blocked', 'timed_out'].includes(latest.status))) {
    return {
      state: 'error' as const,
      message: hasVersion
        ? 'The latest Instant Deck attempt failed. Your previous generated version is still available.'
        : "We couldn't finish the Instant Deck. Your uploaded source is safe, but no generated version was published."
    };
  }
  return {
    state: 'idle' as const,
    message: hasVersion
      ? 'The persisted Instant Deck is ready.'
      : 'Source extraction is ready. Generate the first Instant Deck.'
  };
}
