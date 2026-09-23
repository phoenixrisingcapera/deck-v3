import { z } from 'zod';

const safeDashboardPathPattern = /^\/(?!\/)[^\\\u0000-\u001f]*$/;
export const safeDashboardPathSchema = z.string().regex(safeDashboardPathPattern, 'Expected a same-origin path.');
const nullableUrlString = z.string().url().or(z.string().startsWith('/')).nullable();
const nullableDashboardPathSchema = safeDashboardPathSchema.nullable();

export const workspaceDashboardSchema = z.object({
  greeting: z.object({
    salutation: z.string().min(1),
    userName: z.string().min(1),
    subtitle: z.string().min(1)
  }),
  summaryCards: z.object({
    totalDecks: z.number().int().nonnegative(),
    inProgressDecks: z.number().int().nonnegative(),
    readyForReviewDecks: z.number().int().nonnegative(),
    publishedDecks: z.number().int().nonnegative()
  }),
  workspace: z
    .object({
      id: z.string().min(1),
      name: z.string().min(1)
    })
    .optional(),
  user: z.object({
    id: z.string().min(1),
    handle: z.string().min(1),
    name: z.string().optional(),
    role: z.string().min(1),
    plan: z.string().min(1)
  }),
  stats: z.object({
    uploadedDecks: z.number().int().nonnegative(),
    iterationsThisWeek: z.number().int().nonnegative(),
    slidesInLibrary: z.number().int().nonnegative(),
    teamMembers: z.number().int().nonnegative()
  }),
  latestDeck: z
    .object({
      id: z.string().min(1),
      title: z.string().min(1),
      description: z.string(),
      // DISABLED: Empty intake metadata is valid persisted data.
      // audience: z.string().min(1),
      // purpose: z.string().min(1),
      audience: z.string(),
      purpose: z.string(),
      status: z.enum(['uploaded', 'preparing', 'ready_to_review', 'reviewed', 'exported', 'failed']),
      slideCount: z.number().int().nonnegative(),
      thumbnailUrl: nullableUrlString,
      updatedAt: z.string().min(1)
    })
    .nullable(),
  decks: z.array(
    z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      description: z.string(),
      // DISABLED: Empty intake metadata is valid persisted data.
      // audience: z.string().min(1),
      // purpose: z.string().min(1),
      audience: z.string(),
      purpose: z.string(),
      status: z.enum(['uploaded', 'preparing', 'ready_to_review', 'reviewed', 'exported', 'failed']),
      slideCount: z.number().int().nonnegative(),
      thumbnailUrl: nullableUrlString,
      updatedAt: z.string().min(1)
    })
  ),
  recentDecks: z.array(
    z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      companyName: z.string().nullable(),
      thumbnailUrl: nullableUrlString,
      updatedAt: z.string().min(1),
      status: z.enum(['uploaded', 'preparing', 'ready_to_review', 'reviewed', 'exported', 'failed']),
      statusLabel: z.string().min(1),
      href: safeDashboardPathSchema,
      collaborators: z.array(
        z.object({
          id: z.string().min(1),
          name: z.string().min(1),
          initials: z.string().min(1),
          avatarUrl: nullableUrlString,
          isOwner: z.boolean()
        })
      ),
      extraCollaboratorCount: z.number().int().nonnegative()
    })
  ),
  recentSlides: z.array(
    z.object({
      id: z.string().min(1),
      deckId: z.string().min(1),
      slideNumber: z.number().int().positive(),
      // DISABLED: Extracted slides may remain untitled until review.
      // title: z.string().min(1),
      title: z.string(),
      thumbnailUrl: nullableUrlString,
      previewImageUrl: nullableUrlString,
      status: z.enum(['original', 'edited', 'accepted']),
      updatedAt: z.string().min(1)
    })
  ),
  latestIterations: z.array(
    z.object({
      id: z.string().min(1),
      deckId: z.string().min(1),
      deckTitle: z.string().min(1),
      iterationNumber: z.number().int().positive(),
      title: z.string().min(1),
      scope: z.enum(['whole_deck', 'selected_slides']),
      status: z.enum(['draft', 'ready_for_review', 'accepted', 'compiled', 'failed']),
      thumbnailUrl: nullableUrlString,
      updatedAt: z.string().min(1)
    })
  ),
  recentActivity: z.array(
    z.object({
      id: z.string().min(1),
      type: z.string().min(1),
      title: z.string().min(1),
      subtitle: z.string(),
      deckId: z.string().nullable(),
      href: nullableDashboardPathSchema,
      createdAt: z.string().min(1),
      iconTone: z.enum(['violet', 'blue', 'green', 'amber'])
    })
  ),
  tasks: z.array(
    z.object({
      id: z.string().min(1),
      title: z.string().min(1),
      deckId: z.string().min(1),
      deckTitle: z.string().min(1),
      priority: z.enum(['high', 'medium', 'low']),
      status: z.enum(['open', 'completed']),
      dueAt: z.string().min(1),
      href: safeDashboardPathSchema
    })
  ),
  notifications: z.object({
    unreadCount: z.number().int().nonnegative(),
    items: z.array(
      z.object({
        id: z.string().min(1),
        type: z.string().min(1),
        title: z.string().min(1),
        body: z.string(),
        href: safeDashboardPathSchema,
        deckId: z.string().nullable(),
        createdAt: z.string().min(1),
        read: z.boolean()
      })
    )
  })
});

export function parseWorkspaceDashboard(payload: unknown) {
  return workspaceDashboardSchema.parse(payload);
}
