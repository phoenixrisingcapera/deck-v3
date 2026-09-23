---
title: An agent-native research platform for impact giving
slug: lossless-palmer-ai
kind: proposal-narrative
audience: Jason Palmer (primary) — written to survive being forwarded
status: draft-v1
date_created: 2026-08-21
date_modified: 2026-08-21
publish: false
source_root: /Users/mpstaton/code/lossless-monorepo/astro-knots/sites/mpstaton-site/context-v
source_relative_path: narratives/lossless-palmer-ai/NARRATIVE.md
source_repo_slug: mpstaton-site
collated_at: '2026-08-24'
source_path: "astro-knots/sites/mpstaton-site/context-v/narratives/lossless-palmer-ai/NARRATIVE.md"
---

# An agent-native research platform for impact giving

**The Lossless Group × Palmer AI · August 2026**

> Talk-track note: twelve beats. Beats 5 and 8 are the hinge — if you only
> land two things, land "nothing has to be decided to start" and "agents make
> the plumbing reversible." Beats 3 and 12 are cuttable for time.

---

## 1 — Cover

*An agent-native research platform for impact giving and mission-aligned investing.*

Not a database. Not a dashboard. A research capability you talk to.

---

## 2 — Motivation has a half-life

A principal gets curious about an area of impact — early literacy, workforce
reskilling, rural broadband. That curiosity is a live window, and it is short.

If the answer to *"who's doing good work here?"* takes two weeks, the window
closes. Attention has moved. The gift doesn't happen, or it happens somewhere
worse-researched and louder.

**The whole thesis in one line: the time from *interest* to *five credible
organizations with a story attached* is the variable that determines whether
capital moves at all.**

Everything downstream of this slide is about compressing that interval.

---

## 3 — What that interval looks like today *(cuttable)*

Someone asks. Then: manual searching, half-remembered names, a scramble
through old notes and inboxes, a subscription database that returns rows about
companies rather than organizations doing the work, and finally a document
assembled by hand under time pressure.

Days. Sometimes weeks. And the output is generic — the same paragraph anyone
would have written, for a person whose specific motivation you understood
perfectly well and had no time to write toward.

---

## 4 — The incumbents return rows. The room needs a story.

Pitchbook, Crunchbase, HolonIQ are built for institutional diligence at volume:
screen a thousand, shortlist fifty. They're priced and shaped for deal flow.

That is not this job. Matching an opportunity to a funder at this level is a
**personal conversation or a team meeting.** It needs one organization framed
for one person's actual motivation — the narrative, the framing, the
visualization aimed at the audience in the room.

A query returns rows. A conversation needs a case. No subscription product
makes that leap, because the leap requires knowing the funder, and the tools
don't.

---

## 5 — Two tracks. Nothing has to be decided to start.

This is the structural point, and it's what makes the cost question stop being
a blocker.

- **Track A — capture and content development. Starts immediately, on
  infrastructure already standing.**
- **Track B — the custom application. Runs in parallel, and is not a
  greenfield build.**

The two are connected by agent-written data plumbing (beat 8), which means the
choice of what to run underneath is **reversible.** You are not selecting a
long-term stack today. You are starting work today.

---

## 6 — Track A: this works now

Two roles, both already provisioned:

- A **research aggregation layer** — the canonical record of organizations,
  people, funds, and relationships. *(Currently Twenty.)*
- A **content development hub** — where research becomes drafts, briefs, and
  the narratives that go in front of a funder. *(Currently Outline.)*

Both are live. Both are agent-addressable over API today. That means data
capture and content drafting can begin this week, with agents doing the
gathering and the first-draft writing.

No new spend to start. No decision required. Work product from day one.

> Deliberately framed as *roles* rather than products — if the underlying
> tooling changes, this beat survives unchanged. That's beat 8's promise.

---

## 7 — Track B: the engine already exists

The custom application is not a proposal to start building. Most of it is
built, running, and carrying real data.

**Augment It** — a multi-tenant platform for augmenting entity data with AI:

- Enrichment passes against any record set — custom prompts or source-bound
  research packs — with triage and accept-back-onto-record review
- A **canonical entity layer**: organizations, people, and the affiliation
  edges between them
- An **organization workbench** — search to a canonical org, then work its
  links, streams, corpus, and people in place
- A **corpus curator** — build a strategy or thesis corpus from the canonical
  layer, with live multi-operator sync
- Pluggable web research across multiple search providers, free-tier first

And critically: **it already holds a substantial set of education funders**,
accumulated through the `reach-edu` work. The domain we'd be serving is the
domain the system was fed on.

What's genuinely missing is the last mile — the impact/philanthropy framing,
the funder-matching layer, and the audience-targeted output. Not the engine.

---

## 8 — Agents make the plumbing reversible

The historical reason to agonize over backend choice is migration cost. Pick
wrong, pay for years.

That reason is gone. Coding agents write the SQL and the transforms: from the
aggregation layer into the custom app, and back again. Round trip. What used to
be a quarter of integration work is now an afternoon of supervised agent work.

Near-term that means data moves on demand. As the custom app matures, the same
plumbing runs on a schedule or on events — continuous data fluidity between the
capture surface and the application, without a migration event.

**Therefore no tool we start on is a trap.** Which is exactly why Track A can
begin before any subscription decision is made — and why making that decision
later, with real usage data, is strictly better than making it now.

---

## 9 — The moat is the corpus. The targeting is the product.

Two things no incumbent can copy:

**The corpus.** Deep, specific knowledge of the education and edtech landscape
— who is real, who is early, who has actually moved outcomes, and who merely
presents well. That knowledge is ours, and structured it becomes an asset
rather than a memory.

**The targeting.** One substrate, many outputs. The same underlying research
renders as a memo for one funder, a one-pager for another, a data
visualization for a board, a deck for a meeting — each aimed at a specific
person's actual motivation. Personalization isn't a feature bolted on top; it
is the product.

---

## 10 — What "barebones but functional" means

**Phase 1 — capture (now).** Agents populate the aggregation layer with
organizations, funders, and relationships in the impact/education space.
Content development hub carries the first briefs. Deliverable: faster answers
to live inquiries, immediately.

**Phase 2 — interface.** MCP and API connectors expose the corpus to Claude
Desktop, Mobile, and Web. The interface is a conversation — no new UI to learn,
no seats to sell, no adoption problem.

**Phase 3 — the application.** Augment It's engine, refit for impact giving:
funder-matching, audience-targeted narrative and visualization generation,
scheduled data fluidity with the capture layer.

Each phase is useful standing alone. None requires the next to justify itself.

---

## 11 — The ask

- **Start Track A this week** on the standing infrastructure — no new spend,
  no infrastructure decision.
- **Confirm scope and terms** for the Track B refit.
- **Defer the subscription question** until there's usage data to decide on.

*(Fill in your actual terms, timeline, and engagement shape here before
presenting — this beat is deliberately left for you.)*

---

## 12 — If this works *(cuttable)*

What starts as faster answers to live inquiries becomes the institutional
memory of a giving practice: every organization evaluated, every funder's
motivation understood, every narrative reusable and improvable.

That is the difference between a research subscription and a durable
capability — and it's the kind of asset a serious impact vehicle would be
built on top of, rather than something bought from a vendor.
