import type { Deck } from '$types/domain';
import type { DeckSummary } from '@deck-aistack-codes/shared';
import type { DashboardDeckSummary, DashboardIterationSummary } from '$lib/types/workspace-dashboard';

export function dashboardStatusToDeckSummaryStatus(status: DashboardDeckSummary['status'] | string): DeckSummary['status'] {
  if (status === 'preparing') return 'uploaded';
  if (status === 'ready_to_review') return 'ready';
  if (status === 'exported') return 'reviewed';
  return status as DeckSummary['status'];
}

export function dashboardStatusToDomainDeckStatus(status: DashboardDeckSummary['status'] | string): Deck['status'] {
  if (status === 'preparing') return 'uploaded';
  if (status === 'ready_to_review') return 'ready';
  if (status === 'exported') return 'reviewed';
  return status as Deck['status'];
}

export function dashboardStatusToCardStatus(status: DashboardDeckSummary['status'] | string): Deck['status'] {
  if (status === 'preparing') return 'uploaded';
  if (status === 'ready_to_review') return 'reviewed';
  if (status === 'exported') return 'reviewed';
  return 'ready';
}

export function dashboardIterationStatusLabel(status: DashboardIterationSummary['status']) {
  if (status === 'ready_for_review') return 'Ready to review';
  if (status === 'accepted') return 'Accepted';
  if (status === 'compiled') return 'Compiled';
  if (status === 'failed') return 'Needs attention';
  return 'Draft';
}
