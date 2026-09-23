---
site_uuid: 8cd16db4-2590-4f05-abab-d090a5adfc9a
hex_code: bqnbpp
title: Old Git History May Hold Detail Clients Would Rather We Kept Quiet
lede: Nothing is exposed today. But we write candidly about client work, and a few
  older commits probably say more than a client would choose to say themselves. Worth
  tidying when there's a natural window — not worth a fire drill.
summary: Housekeeping item. Working trees and published surfaces are clean; this is
  only about commit history in a handful of repos, where older entries may name specifics
  a client would prefer to keep to themselves. Low urgency and no known access by
  anyone outside the team. Records why it is worth doing eventually, what doing it
  actually costs, and the deliberate decision not to enumerate specifics in this document.
  Read before planning any history rewrite, and before adding detail here.
publish: false
date_created: 2026-08-17
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
date_authored_final_draft: null
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 5 (1M context)
at_semantic_version: 0.0.1.0
status: Open
tags:
- Tech-Debt
- Git-History
- Client-Courtesy
- Housekeeping
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: issues/Old-Git-History-May-Hold-Detail-Clients-Would-Rather-We-Kept-Quiet.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/issues/Old-Git-History-May-Hold-Detail-Clients-Would-Rather-We-Kept-Quiet.md"
---

# Old Git History May Hold Detail Clients Would Rather We Kept Quiet

## Why care?

We write candid changelogs. That is a deliberate practice and a good one — it is
why the corpus is worth anything. The side effect is that when we are working on
a client engagement, the candid account sometimes includes specifics the client
would not have chosen to publish about themselves.

Current state is clean. Working trees, rendered sites, and roll-ups have all
been screened and corrected. **This issue is only about commit history**, where
older versions of those files still sit.

It is a courtesy item, not an incident. Nobody outside the team is known to have
looked, most of the repos involved are ones only we clone, and none of it is the
kind of material that causes harm on its own. But "technically still in the
history" is not the posture we would want to explain to a client who asked, and
being good about this is part of being the kind of shop people hand their
fundraise materials to.

## What this document deliberately does not say

**No specifics here.** No client names, no repo names, no commit ranges, no
description of what the detail actually is.

That is on purpose and should stay that way. A document that enumerates where
sensitive material is buried is a more useful artifact to the wrong reader than
the buried material itself — it turns a needle-in-a-haystack into an index. This
file exists to make sure the task is not forgotten, not to make it easy to
exploit.

Whoever picks this up will need to re-derive the specifics. That is a feature.
The screening recipe in the frontmatter handoffs (grep families for credentials,
named entities, financial figures) is the same one that found these, and it runs
in a couple of minutes.

This file is `publish: false` and lives in the anchor monorepo, which is private.
**Keep it here.** Do not copy it into a child repo, and do not let it into a
roll-up — several children are public.

## Why it is not urgent

- Nothing is reachable from a rendered page, an index, or a search result. It
  requires deliberately reading old commits.
- The material is commercially sensitive rather than dangerous — no live
  credentials, no personal data, nothing that creates risk for an individual.
- The repos most likely to be involved are not ones outsiders clone.

## Why it is still worth doing

- A client who found it would be entitled to be annoyed, and "it's only in the
  history" is a weak answer.
- Some of this concerns other people's confidential business, which is not ours
  to have left lying around, however inertly.
- It gets harder the longer it waits. Every new commit pushes it further back
  and adds more refs that would need rewriting.

## What it would actually take

History rewriting is the destructive end of git, so this wants a deliberate
window rather than an idle afternoon.

1. **Re-derive the specifics** — run the screening greps across each candidate
   repo's history, not just its working tree.
2. **Decide the tool** — `git filter-repo` is the current recommendation
   (`filter-branch` is deprecated and slow). Redacting content is usually
   better than dropping commits wholesale, which loses authorship history.
3. **Coordinate.** A rewrite changes every commit SHA after the touched point.
   Anyone with a clone has to re-clone or hard-reset. Submodule pointers in
   parent repos will need updating, since they reference SHAs that no longer
   exist. **This is the expensive part, not the rewrite itself.**
4. **Force-push**, then confirm forks and any GitHub Pages deployments picked up
   the change.
5. **Check the caches.** Rewritten commits can remain reachable through the
   GitHub API for a while; support can be asked to purge them.

## The preventive half, which is already done

The exposures that prompted this have had their causes fixed, so this is a
backlog item rather than an open wound:

- Roll-up scripts no longer treat a `publish: true` flag as permission to
  aggregate. Publication now gates on repository visibility and on whether the
  source is client work, and it fails closed.
- The confidentiality screen runs *before* a publish value is set on a client
  repo, rather than after.
- Client engagements are excluded from public aggregation structurally, by where
  they live in the tree, rather than by a list someone has to remember to update.

## See also

- [[Frontmatter-Normalization-Remaining-Repos]] — carries the screening recipe
- [[Frontmatter-Normalization-The-Context-V-Tier]] — the same screen applied to
  the tier that has not been swept yet
