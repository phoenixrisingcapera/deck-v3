---
title: Browser-drive verification — agents click the buttons before a human walks
  the surface
lede: Agents prove the buttons work with Playwright MCP before a human judges whether
  the surface is usable.
date_created: 2026-07-22
date_modified: 2026-07-22
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Fable 5
semantic_version: 0.0.0.1
tags:
- Blueprint
- Browser-Automation
- Playwright-MCP
- Claude-Chrome
- Verification
- Agent-Sessions
- MCP
status: Draft
site_uuid: b680d87a-9b11-48c8-81e0-e2564501bb66
hex_code: gbg2fx
date_authored_initial_draft: 2026-07-22
date_authored_current_draft: 2026-07-22
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: blueprints/Browser-Drive-Verification-For-Agent-Sessions.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/blueprints/Browser-Drive-Verification-For-Agent-Sessions.md"
---

# Browser-drive verification for agent sessions

## Why care?

Agent sessions across the Lossless tree already verify code the scripted way — typechecks, builds, smoke curls, service-level proofs over NATS or HTTP. But every UI-bearing phase used to end at the same cliff: "operator browser walk-through," a rung only a human could climb. That conflates two different questions. **Whether the buttons work** is mechanical and scriptable. **Whether the surface is usable** is judgment and stays human. This blueprint gives agents the first question, so humans only get asked the second.

The pattern was identified during the Augment-from-DB run in `ai-labs/augment-it` (five UI-bearing phases, each ending with a named-but-unautomated walk-through — see that repo's `context-v/loops/Loop-through-Spec-Write-Plans-Implement-Test-Changelog-Commit.md`, whose test ladder this blueprint slots into as "rung 5.5").

## The two tiers

| Tier | Tool | When | Character |
|---|---|---|---|
| **Codified** (default) | **Playwright MCP** (`@playwright/mcp`) | The repeatable per-phase click-path: navigate → click → type → assert | Semantic locators, accessibility-tree snapshots (token-cheap vs raster), DOM assertions, headless-capable — runs without anyone watching |
| **Interactive** | **Claude Code Chrome integration** (`claude --chrome`, or `/chrome` → enable by default) | Exploratory or pairing sessions — "open it and show me" | Drives the operator's real Chrome; screenshots/GIFs, console + network logs; shares auth state with the human's browser |

(Full desktop computer-use also exists in Claude Code on macOS via `/mcp`, but everything in this tree's verification needs is web content — the browser tiers cover it.)

## Setup — per repo, project scope

Per the tree-wide MCP convention (project scope, never local — local scope has lost config here before):

```bash
claude mcp add -s project playwright -- npx @playwright/mcp@latest
```

This lands in the repo's committed `.mcp.json`, so every collaborator and every future session inherits it. **Newly added MCP servers load in the NEXT session, not the current one** — same rule as skills symlinks.

## The discipline

1. **Reads are unrestricted; writes are gated.** A browser drive may click freely through navigation, search, reveals, and any read-shaped surface. Browser-driven **writes** happen only against designated safe targets (in augment-it: the Aspen Institute card, seeded as the standing test entity) — never mint test entities in shared or canonical data. This is the same write-discipline the service-level proofs follow, moved up a layer.
2. **Snapshots over screenshots.** Accessibility-tree snapshots are the default evidence; raster screenshots only when the question is visual (layout, theme, overlap). Screenshots are token-expensive and diff-hostile.
3. **The drive script is named in the plan.** Whatever doc-shape a repo uses for phase plans, the browser click-path belongs there *before* implementation — the same discipline as naming verification before writing code. A drive that exists only in a session transcript is not codified.
4. **Augments, never replaces, the human rung.** The browser drive proves the mechanics; the human walk-through judges usability, copy, and feel. Both rungs stay on the ladder; the human one just stops being asked to catch broken buttons.
5. **Dev-server reality.** The drive runs against the same locally-running stack the smoke tests hit. If the target app is federated microfrontends, all required remotes must be up — a drive against a half-up federation reports mount errors, not product truth.

## Adoption checklist (per repo)

- [ ] `claude mcp add -s project playwright -- npx @playwright/mcp@latest` → commit `.mcp.json`
- [ ] Add the browser-drive block to the repo's `CLAUDE.md` (the canonical block lives in the anchor root `CLAUDE.md` — copy it verbatim)
- [ ] Name a **safe write target** for the repo (or declare the repo read-only-drive)
- [ ] If the repo has a loop/plan convention, add the drive as an explicit rung between scripted E2E and the human walk-through

## Related

- `ai-labs/augment-it/context-v/loops/Loop-through-Spec-Write-Plans-Implement-Test-Changelog-Commit.md` — the proving-ground loop this slots into (rung 5.5)
- `ai-labs/context-vigilance-kit/context-v/blueprints/Browser-Drive-Verification-For-Agent-Sessions.md` — the kit's operationalization draft (rollout tooling, core-MCP registry)
- Anchor root `CLAUDE.md` §Browser-drive verification — the instruction block every Lossless `CLAUDE.md` carries
- [[Source-Curation-Gate]] — sibling blueprint; same "structure the human's judgment, automate the mechanical" ethos
