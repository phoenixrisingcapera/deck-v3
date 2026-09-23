export interface DashboardUserSummary {
  id: string;
  handle: string;
  name?: string;
  role: string;
  plan: string;
}

export interface DashboardGreeting {
  salutation: string;
  userName: string;
  subtitle: string;
}

export interface DashboardSummaryCards {
  totalDecks: number;
  inProgressDecks: number;
  readyForReviewDecks: number;
  publishedDecks: number;
}

export interface DashboardCollaborator {
  id: string;
  name: string;
  initials: string;
  avatarUrl: string | null;
  isOwner: boolean;
}

export interface DashboardRecentDeck {
  id: string;
  title: string;
  companyName: string | null;
  thumbnailUrl: string | null;
  updatedAt: string;
  status: 'uploaded' | 'preparing' | 'ready_to_review' | 'reviewed' | 'exported' | 'failed';
  statusLabel: string;
  href: string;
  collaborators: DashboardCollaborator[];
  extraCollaboratorCount: number;
}

export interface DashboardActivityItem {
  id: string;
  type: string;
  title: string;
  subtitle: string;
  deckId: string | null;
  href: string | null;
  createdAt: string;
  iconTone: 'violet' | 'blue' | 'green' | 'amber';
}

export interface DashboardTaskItem {
  id: string;
  title: string;
  deckId: string;
  deckTitle: string;
  priority: 'high' | 'medium' | 'low';
  status: 'open' | 'completed';
  dueAt: string;
  href: string;
}

export interface DashboardNotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  href: string;
  deckId: string | null;
  createdAt: string;
  read: boolean;
}

export interface DashboardNotificationsSummary {
  unreadCount: number;
  items: DashboardNotificationItem[];
}

export interface DashboardDeckSummary {
  id: string;
  title: string;
  description: string;
  audience: string;
  purpose: string;
  // UPDATED: `failed` is a canonical backend state and must remain visible
  // instead of invalidating the complete dashboard response.
  status: 'uploaded' | 'preparing' | 'ready_to_review' | 'reviewed' | 'exported' | 'failed';
  slideCount: number;
  thumbnailUrl: string | null;
  updatedAt: string;
}

export interface DashboardSlidePreview {
  id: string;
  deckId: string;
  slideNumber: number;
  title: string;
  thumbnailUrl: string | null;
  previewImageUrl: string | null;
  status: 'original' | 'edited' | 'accepted';
  updatedAt: string;
}

export interface DashboardIterationSummary {
  id: string;
  deckId: string;
  deckTitle: string;
  iterationNumber: number;
  title: string;
  scope: 'whole_deck' | 'selected_slides';
  status: 'draft' | 'ready_for_review' | 'accepted' | 'compiled' | 'failed';
  thumbnailUrl: string | null;
  updatedAt: string;
}

export interface DashboardStats {
  uploadedDecks: number;
  iterationsThisWeek: number;
  slidesInLibrary: number;
  teamMembers: number;
}

export interface WorkspaceDashboardResponse {
  greeting: DashboardGreeting;
  summaryCards: DashboardSummaryCards;
  workspace?: {
    id: string;
    name: string;
  };
  user: DashboardUserSummary;
  stats: DashboardStats;
  latestDeck: DashboardDeckSummary | null;
  decks: DashboardDeckSummary[];
  recentDecks: DashboardRecentDeck[];
  recentSlides: DashboardSlidePreview[];
  latestIterations: DashboardIterationSummary[];
  recentActivity: DashboardActivityItem[];
  tasks: DashboardTaskItem[];
  notifications: DashboardNotificationsSummary;
}
