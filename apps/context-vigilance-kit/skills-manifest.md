---
title: Context Vigilance Kit — Skills Manifest
description: Inventory of agent skills (Anthropic agent-skills spec) discovered under
  any context-v/skills/ directory in the curated sources. Tracked separately from
  the corpus manifest.
date_generated: '2026-07-21'
schema_version: 1
summary:
  total_skills: 27
  with_skill_md: 24
  without_skill_md: 3
  by_repo:
    lossless-monorepo: 27
  by_completeness:
    complete: 14
    skill-md-only: 6
    missing-required-fields: 4
    no-skill-md: 3
skills:
- name: astro-knots
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/astro-knots
  path_from_monorepo_root: context-v/skills/astro-knots
  has_skill_md: true
  skill_md_frontmatter:
    name: astro-knots
    description: The Lossless Group's Astro Knots conventions — vision, tech hierarchy,
      approved frameworks, and hard prohibitions for the family of ~10+ Astro sites
      and the Lossless Flavored Markdown ecosystem. Use whenever working on an Astro
      project in the lossless-monorepo (or any sibling repo), scaffolding new sites,
      choosing dependencies, building components, integrating LFM, or when the user
      mentions "Astro Knots", "LFM", "Lossless Flavored Markdown", or "pseudomonorepo".
      Hard prohibitions on React, JSX, Angular, and unnecessary dependencies.
  skill_md_body_lines: 200
  missing_required_fields: []
  asset_counts:
    references_md: 7
    templates_files: 0
    scripts_files: 0
    total_md: 8
  completeness: complete
- name: changelog
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/changelog
  path_from_monorepo_root: context-v/skills/changelog
  has_skill_md: false
  skill_md_frontmatter: {}
  skill_md_body_lines: 0
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 9
  completeness: no-skill-md
- name: changelog-conventions
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/changelog-conventions
  path_from_monorepo_root: context-v/skills/changelog-conventions
  has_skill_md: true
  skill_md_frontmatter:
    name: changelog-conventions
    description: How The Lossless Group writes and structures changelog/ entries across
      all repos (projects, true monorepos, pseudomonorepos). Use whenever shipping
      or pushing a coherent chunk of work, when scaffolding a new repo's changelog/
      directory, when authoring a product release message, when the user says "log
      this", "write a changelog", or "ship note", or when reviewing a changelog/ file.
      Encodes the strict frontmatter (publish, lede, ISO dates), filename pattern,
      "it exists" priority, and the show-don't-enforce ethos.
  skill_md_body_lines: 241
  missing_required_fields: []
  asset_counts:
    references_md: 5
    templates_files: 2
    scripts_files: 0
    total_md: 8
  completeness: complete
- name: chroma-agent-skills
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/chroma-agent-skills
  path_from_monorepo_root: context-v/skills/chroma-agent-skills
  has_skill_md: false
  skill_md_frontmatter: {}
  skill_md_body_lines: 0
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 4
    total_md: 61
  completeness: no-skill-md
- name: competitive-analysis
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/competitive-analysis
  path_from_monorepo_root: context-v/skills/competitive-analysis
  has_skill_md: true
  skill_md_frontmatter:
    title: Competitive Analysis Taxonomy
    lede: 'Two orthogonal axes for classifying a target company''s competitors: the
      stage ring (concentric circles outward from the target''s own stage) and the
      competitor type (direct / adjacent / indirect / noisewashing). Reference for
      humans and for any agent writing the competitive landscape section.'
    date_authored_initial_draft: 2026-06-09
    at_semantic_version: 0.0.0.1
    usage_index: 0
    publish: false
    category: Reference
    tags:
    - Competitive-Analysis
    - Taxonomy
    - Investment-Memo
    - Stage-Rings
    - Competitor-Types
    authors:
    - Michael Staton
    augmented_with: Claude Code (Opus 4.7)
  skill_md_body_lines: 109
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: missing-required-fields
- name: context-vigilance
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/context-vigilance
  path_from_monorepo_root: context-v/skills/context-vigilance
  has_skill_md: true
  skill_md_frontmatter:
    name: context-vigilance
    description: Lossless Group's framework for managing context-v/ directories in
      any project. Use whenever creating, updating, or organizing files in any context-v/
      folder (specs, plans, prompts, blueprints, reminders, agent-skills, explorations,
      issues — plus the universal extra/ and sitemap/, and the experimental loops/,
      handoffs/, decisions/, and contracts/), or when the user asks about context
      engineering, AI co-development workflow, or the "context-v" convention. Enforces
      directory roles, the four-part epoch.major.minor.patch versioning, YAML frontmatter
      standard, wikilink cross-references, and the prep/reflective/journey cognitive
      modes.
  skill_md_body_lines: 233
  missing_required_fields: []
  asset_counts:
    references_md: 6
    templates_files: 6
    scripts_files: 0
    total_md: 13
  completeness: complete
- name: crawl-fetch-ingest
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/crawl-fetch-ingest
  path_from_monorepo_root: context-v/skills/crawl-fetch-ingest
  has_skill_md: true
  skill_md_frontmatter:
    name: crawl-fetch-ingest
    description: The Lossless Group's workflow for filling in team and portfolio metadata
      for VC firms and the operating companies they back — crawl a firm's site, fetch
      structured data + brand assets for people and companies referenced in a deck/PDF,
      ingest as canonical .md files with YAML frontmatter. Supports two starting anchors
      — firm-anchored (one VC → its team → its portfolio → portco CEOs) and company-anchored
      (one operating company → its backer firms → each backer's team + portfolio,
      stopping there) — for credibility-card use. Use whenever you need to recreate
      VC team pages, advisor sections, or portfolio company sections in HTML/Tailwind/Reveal
      slideshows; whenever the input is "here's a PDF and/or a firm URL, fill in the
      people and companies"; whenever you need headshots, LinkedIn URLs, company logos
      (SVG preferred), CEO metadata; whenever you need to "ingest our backers" or
      "make these investors legible to readers"; whenever the user mentions "fill
      out the team", "find the headshots", "credibility ingest", "we need their portfolio
      companies", or names this skill directly. Encodes the four-checkpoint cascade
      (VC team → advisors → portfolio companies → portco CEOs), the cross-tool fallback
      pattern (Firecrawl → Tavily → OpenGraph.io), the global-cache-per-firm convention
      so the same firm's data is reused across multiple decks/memos, and the loose
      canonical schema that sites converge toward on refactor (not enforced on ingest).
  skill_md_body_lines: 304
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 8
    total_md: 24
  completeness: complete
- name: decile-hub-connector
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/decile-hub-connector
  path_from_monorepo_root: context-v/skills/decile-hub-connector
  has_skill_md: true
  skill_md_frontmatter:
    name: decile-hub-connector
    description: How augment-it (and any Lossless VC-client workspace) talks to the
      Decile Hub API — the first per-client custom connector. Use whenever pulling
      from or pushing to Decile Hub (people, organizations, pipeline prospects, deal
      shares, deal memos, funds/entities, portfolio companies, capital accounts, notes,
      tasks, files, events), wiring the Decile connector for a new client, building
      or maintaining the decile-mcp server, mapping Decile records into the SurrealDB
      canonical layer, or when the user mentions "Decile", "DecileHub", "DECILE_API_URL",
      "DECILE_HUB_API_KEY", or a per-client CRM connector. Encodes the auth (raw API
      token in the Authorization header — no Bearer), the per-tenant subdomain base
      URL, the THREE distinct pagination patterns, the upsert-by-natural-key write
      semantics, the custom_data_points / variables (merge-tag) system, and the mapping
      of Decile people/organizations onto the SurrealDB canonical persons/organizations
      tables. The authoritative contract is the on-disk OpenAPI spec; this skill is
      the operating guide on top of it.
  skill_md_body_lines: 143
  missing_required_fields: []
  asset_counts:
    references_md: 1
    templates_files: 0
    scripts_files: 0
    total_md: 2
  completeness: complete
- name: deck-iteration-workflow
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/deck-iteration-workflow
  path_from_monorepo_root: context-v/skills/deck-iteration-workflow
  has_skill_md: true
  skill_md_frontmatter:
    name: deck-iteration-workflow
    description: The Lossless Group's workflow for developing slides-only Astro sites
      for fundraise processes, aligned with the calmstorm-decks project patterns and
      the iterative approach from the "Develop a Slides-only Astro Site for a Fundraise
      Process" specification. Use when creating or modifying slide decks, managing
      slide variants, or implementing the structured iteration workflow for fundraise
      material development.
  skill_md_body_lines: 193
  missing_required_fields: []
  asset_counts:
    references_md: 1
    templates_files: 2
    scripts_files: 0
    total_md: 4
  completeness: complete
- name: generate-consistent-og-images
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/generate-consistent-og-images
  path_from_monorepo_root: context-v/skills/generate-consistent-og-images
  has_skill_md: true
  skill_md_frontmatter: {}
  skill_md_body_lines: 381
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 2
    scripts_files: 0
    total_md: 1
  completeness: missing-required-fields
- name: gh-cli-projects-tasks-conventions
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/gh-cli-projects-tasks-conventions
  path_from_monorepo_root: context-v/skills/gh-cli-projects-tasks-conventions
  has_skill_md: true
  skill_md_frontmatter:
    name: gh-cli-projects-tasks-conventions
    description: How The Lossless Group uses the `gh project` CLI (GitHub Projects
      v2) to manage tasks across the pseudomonorepo tree. Use whenever creating, editing,
      or listing GitHub Project tasks via `gh project item-create`, `gh project item-add`,
      or `gh project item-edit`; whenever the user mentions "gh project", "create
      a task", "add to the project", "draft a project item", "ProjectV2", or asks
      to script project task creation; whenever an agent is about to author a task
      body that references one or more `context-v/` files. Encodes the **task-body-is-a-github-link**
      convention — every task whose work-context lives in a `context-v/` file gets
      a body whose primary content is a clickable GitHub URL to that file in its own
      repo (NOT a deep path inside the parent monorepo, because each pseudomonorepo
      level is its own git repo and the URL must respect that). Composes with the
      `pseudomonorepos` skill to identify which repo a local context-v path belongs
      to and which branch tier (`development` / `main` / `master`) the link should
      target.
  skill_md_body_lines: 250
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: git-conventions
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/git-conventions
  path_from_monorepo_root: context-v/skills/git-conventions
  has_skill_md: true
  skill_md_frontmatter:
    name: git-conventions
    description: The Lossless Group's git commit message conventions — structured
      headers with action verbs and effort groupings, paragraph-spaced bodies that
      explain impact before implementation, and "Also included" riders for minor changes.
      Use when writing commit messages, reviewing commits, or when the user mentions
      "commit message format", "git conventions", or asks how to structure a commit.
  skill_md_body_lines: 296
  missing_required_fields: []
  asset_counts:
    references_md: 3
    templates_files: 0
    scripts_files: 0
    total_md: 4
  completeness: complete
- name: lossless-flavored-markdown
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/lossless-flavored-markdown
  path_from_monorepo_root: context-v/skills/lossless-flavored-markdown
  has_skill_md: true
  skill_md_frontmatter:
    name: lossless-flavored-markdown
    description: The Lossless Group's extended-markdown flavor — what LFM is, when
      to use it, how its directives normalize across syntaxes (CommonMark, GFM, Obsidian
      callouts, remark-directive, Markdoc), how citations and link previews work,
      and how sites extend it via trigger maps and theme tokens. Use whenever authoring
      or rendering content in any Astro Knots site, integrating the @lossless-group/lfm
      package, building or registering custom components for markdown, debugging callouts/embeds/citations,
      or when the user mentions "LFM", "Lossless Flavored Markdown", "extended markdown",
      "directive syntax", "wikilink", "trigger map", "callout", or "hex-code citation".
  skill_md_body_lines: 153
  missing_required_fields: []
  asset_counts:
    references_md: 5
    templates_files: 0
    scripts_files: 0
    total_md: 6
  completeness: complete
- name: maintain-design-md
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/maintain-design-md
  path_from_monorepo_root: context-v/skills/maintain-design-md
  has_skill_md: true
  skill_md_frontmatter:
    name: maintain-design-md
    description: How to author and maintain a `DESIGN.md` file at the root of any
      Lossless project (site, splash page, plugin landing, fundraise deck) following
      Google Stitch's open spec. Use whenever a project is missing a `DESIGN.md` and
      an agent needs the project's visual identity in machine-readable form; whenever
      the user mentions "design tokens", "design system", "DESIGN.md", or "Stitch
      spec"; whenever theme/CSS-token work changes the runtime values (new CSS custom
      property in `:root`, renamed token, new mode, new component pattern, refreshed
      palette, refreshed typography scale) and the documented contract has drifted;
      whenever a sibling skill (`generate-consistent-og-images`, `theme-system`, `astro-knots`)
      needs to read locked design values; whenever the user says "the agent doesn't
      know what color we use" or "let's write down the design system." Encodes (1)
      the Stitch spec's frontmatter token groups (colors, typography, rounded, spacing,
      components) and the eight prose sections in canonical order, (2) the maintenance
      triggers — what kinds of code changes should bounce back into the document,
      (3) the "runtime CSS is source of truth, DESIGN.md is the contract" discipline,
      (4) the precedent for off-spec extensions like an `imagery:` block, (5) anti-patterns.
      The skill never sees an API key or makes network calls — it's a pure-document
      discipline.
  skill_md_body_lines: 219
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 1
    scripts_files: 0
    total_md: 2
  completeness: complete
- name: maintain-filemap
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/maintain-filemap
  path_from_monorepo_root: context-v/skills/maintain-filemap
  has_skill_md: true
  skill_md_frontmatter:
    name: maintain-filemap
    description: Use whenever the directory shape of a Lossless pseudomonorepo (or
      any child repo) changes — a new top-level directory is added, a submodule is
      mounted or unmounted, a major subsystem is renamed — or on a weekly cadence,
      or before any release that would land on GitHub, to regenerate the `FILEMAP.md`
      at each affected repo's root so collaborators see the current shape without
      cloning. Triggers when the user mentions "filemap", "tree", "directory layout",
      "repo overview", "what does this repo even contain", "new collaborator joining";
      also when the agent itself proposes adding/removing a top-level dir or a submodule,
      because that's exactly the moment the discipline matters.
  skill_md_body_lines: 105
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 1
    total_md: 1
  completeness: complete
- name: maintain-splash-pages
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/maintain-splash-pages
  path_from_monorepo_root: context-v/skills/maintain-splash-pages
  has_skill_md: true
  skill_md_frontmatter:
    name: maintain-splash-pages
    description: The Lossless Group's pattern for repo-level splash pages — small
      Astro sites at <repo>/splash/ that ship to GitHub Pages on push to main, render
      the repo's changelog/ + context-v/ alongside curated marketing copy, and stay
      isolated from any package the repo also publishes. Use proactively whenever
      scaffolding a noteworthy new repo (every "important" repo wants one), when shipping
      a coherent chunk of work that an external reader would land on, when adding
      a feature (search, sort, tags row, theme mode) to an existing splash, when converting
      a legacy apps/<name>/ site to splash/, when troubleshooting a Pages deploy,
      or when the user mentions "splash", "GitHub Pages", "lossless-group.github.io",
      "Pagefind on our site", or working under a splash/ directory. Codifies the proven
      shape across three reference implementations (memopop-site, content-farm/splash,
      lfm/splash) and the package-isolation discipline that keeps splashes safe to
      add to repos that also publish to JSR/npm.
    status: Draft
  skill_md_body_lines: 423
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: market-capture-analysis
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/market-capture-analysis
  path_from_monorepo_root: context-v/skills/market-capture-analysis
  has_skill_md: true
  skill_md_frontmatter:
    title: Market Capture Analysis
    lede: 'Answers the first of the two foundational VC questions — *how big can it
      get?* — by walking revenue and EBITDA across penetration steps of SAM/SOM/TAM
      at the company''s existing pricing and business model. A static if-then picture:
      the size of the prize at each penetration step, with assumptions named so they
      can be challenged. Pairs with the sibling skill [[timeline-scenario-analysis]],
      which answers *how fast?*'
    date_authored_initial_draft: 2026-06-09
    at_semantic_version: 0.0.0.1
    usage_index: 0
    publish: false
    category: Reference
    tags:
    - Market-Capture
    - TAM-SAM-SOM
    - Penetration-Grid
    - Revenue-Modeling
    - Investment-Memo
    authors:
    - Michael Staton
    augmented_with: Claude Code (Opus 4.7)
  skill_md_body_lines: 86
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: missing-required-fields
- name: open-graph-share-seo-geo
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/open-graph-share-seo-geo
  path_from_monorepo_root: context-v/skills/open-graph-share-seo-geo
  has_skill_md: true
  skill_md_frontmatter:
    name: open-graph-share-seo-geo
    description: How to make a page unfurl reliably in iMessage, WhatsApp, Slack,
      Discord, LinkedIn, and X; surface to search engines via sitemap.xml + robots.txt;
      and stay legible to generative engines (GEO), including the llms.txt standard
      for LLM corpus ingest. Use when adding or debugging OpenGraph / Twitter Card
      metadata, picking an OG image format, choosing where to host the image, fixing
      pages that "won't unfurl", auditing share previews, scaffolding /llms.txt and
      /llms-full.txt, or adding @astrojs/sitemap + robots.txt to a splash or marketing
      site. Encodes the JPEG-over-WebP rule, the ImageKit content-negotiation gotcha,
      the absolute-URL requirement, the og:image:type-must-match-bytes invariant,
      the cache-busting recipe for forcing a re-unfurl, the prose-in-markdown source-of-truth
      pattern for llms.txt, and the sitemap filter that keeps non-HTML routes (llms.txt,
      404) out of the search-engine index.
  skill_md_body_lines: 420
  missing_required_fields: []
  asset_counts:
    references_md: 5
    templates_files: 0
    scripts_files: 0
    total_md: 6
  completeness: complete
- name: overlay-svg-text
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/overlay-svg-text
  path_from_monorepo_root: context-v/skills/overlay-svg-text
  has_skill_md: true
  skill_md_frontmatter:
    name: overlay-svg-text
    description: How to overlay on-brand SVG text on Lossless OG / share imagery —
      Hack Bold gradient-filled h1, thin sans eyebrow, Poor Story handwritten note.
      Use whenever a generated OG image needs title/eyebrow/sub text composited on
      top before it ships (the empty-region zone from `generate-consistent-og-images`
      is the canvas this skill paints into), whenever an unfurl preview looks too
      anonymous without a wordmark or subtitle, whenever a fundraise-deck slide needs
      a brand-flavored title overlay on a hero image, whenever the user says "overlay
      text on the OG image", "add a title to the banner", "make the unfurl say something",
      "drop a wordmark on this", or names this skill directly. Encodes the brand-wide
      type system (Hack Bold for gradient h1, thin sans for eyebrow, Poor Story for
      handwritten notes), the per-site gradient-from-DESIGN.md discipline (the brand
      SVGs are raster-baked references, not editable gradient sources — the editable
      gradient lives in each project's DESIGN.md), the canonical SVG fill-with-gradient
      pattern (simpler and more portable than mask/union for this use case), and the
      sharp-based compositing pipeline that writes JPEG-out for delivery per the open-graph-share-seo-geo
      skill.
  skill_md_body_lines: 275
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 2
    scripts_files: 0
    total_md: 1
  completeness: complete
- name: pseudomonorepos
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/pseudomonorepos
  path_from_monorepo_root: context-v/skills/pseudomonorepos
  has_skill_md: true
  skill_md_frontmatter:
    name: pseudomonorepos
    description: The Lossless Group's coined term and pattern — parent repos that
      aggregate child repos (often as git submodules) primarily to host a parent-level
      context-v/. Use whenever working anywhere in lossless-monorepo or its descendants,
      when starting any new task that might overlap with prior work, when scaffolding
      a new project, when the user mentions "pseudomonorepo", "submodule", "context-v",
      or names of the children (ai-labs, astro-knots, content-farm, tidyverse), AND
      ALWAYS when the user proposes to move/relocate/re-clone/re-nest a repo within
      the tree (which triggers the HARD STOP three-precondition checklist — local
      branches synced, remote branches catalogued, gitignored secrets backed up).
      Encodes the search-first-before-creating behavior, the tree-walking discipline,
      and the relocation-safety protocol.
  skill_md_body_lines: 331
  missing_required_fields: []
  asset_counts:
    references_md: 6
    templates_files: 0
    scripts_files: 0
    total_md: 7
  completeness: complete
- name: search-lossless-corpus
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/search-lossless-corpus
  path_from_monorepo_root: context-v/skills/search-lossless-corpus
  has_skill_md: true
  skill_md_frontmatter:
    name: search-lossless-corpus
    description: Use whenever the user asks a question that prior work might already
      have answered — "what did we decide about X", "when did we ship X", "why did
      we choose X over Y", "has this failed before", "where did we put X" — and generally
      to ground answers in The Lossless Group's own corpus instead of training-data
      folklore. Encodes the four local Chroma collections (`context-vigilance-corpus`,
      `lossless-changelog`, `claude-code-sessions`, `claude-code-tool-traces`) reachable
      via the `chroma` MCP server, the four-step agentic-search loop (decompose →
      execute → evaluate → synthesize), the citation discipline (source path + timestamp
      + repo slug for every claim), and the metadata-filter patterns that make queries
      precise. Triggers on questions about prior decisions, shipped work, past Claude
      Code sessions, recurring tool failures, or any "did we already…" framing. Does
      not cover Chroma setup, ingestion pipelines, or maintenance — those are handled
      by [[chroma-local]] and the [[context-vigilance-kit]] scripts.
  skill_md_body_lines: 154
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: slide-target
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/slide-target
  path_from_monorepo_root: context-v/skills/slide-target
  has_skill_md: true
  skill_md_frontmatter:
    name: slide-target
    description: Load the full working context for ONE DidiDecks slide (deck/variant/slot)
      so an agent can iterate on it slide-by-slide without re-explaining where things
      live. The first of the `slide-*` skill family (target → improve → rank → decompose).
      Use whenever the user wants to work on a specific slide of a DidiDecks/Astro
      deck — "let's work on slide 2", "fix this card", "/slide-target rural-income
      v1 02", "go slide by slide", "target the funder-pipeline slide" — or when iterating
      on a client-site deck under dididecks-ai (reach-edu-hub, chroma-decks, etc.).
      Assembles the section file, the slides.ts slot, the narrative slot, the rank/audit
      status, the live URLs, and the design-system tokens for exactly that slide,
      then scopes all work to it. Composes with deck-iteration-workflow and theme-system.
  skill_md_body_lines: 98
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: splash
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/splash
  path_from_monorepo_root: context-v/skills/splash
  has_skill_md: false
  skill_md_frontmatter: {}
  skill_md_body_lines: 0
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 305
  completeness: no-skill-md
- name: study-repos-first
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/study-repos-first
  path_from_monorepo_root: context-v/skills/study-repos-first
  has_skill_md: true
  skill_md_frontmatter:
    name: study-repos-first
    description: The Lossless Group's discipline of pinning a curated collection of
      upstream repos (a "study") around a domain question *before* designing or coding
      in that domain. Use when starting work that touches conventions, file formats,
      schemas, protocols, or any decision where prior art exists; when the user mentions
      "study", "studies/", "reference collection", "prior art", "pin a submodule",
      or names of existing studies (open-specs-and-standards, memory-layers-for-agents,
      data-analytics-specifications-and-standards); when scaffolding a new study,
      extending one, or deciding whether something belongs in a study vs. a project.
      Encodes the "read upstream code, don't paraphrase from training data" behavior.
  skill_md_body_lines: 117
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: surrealdb-canonical-layer
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/surrealdb-canonical-layer
  path_from_monorepo_root: context-v/skills/surrealdb-canonical-layer
  has_skill_md: true
  skill_md_frontmatter:
    name: surrealdb-canonical-layer
    description: Verify a SurrealDB-backed canonical layer directly, over the `surrealdb`
      MCP server, instead of writing a disposable Node script per check. Use whenever
      the user asks to confirm a batch of writes landed correctly ("did the FreedomFest
      speakers get tagged right", "do these people have an org relationship", "check
      that event's rows aren't duplicated"), whenever a new client/event/import needs
      its data audited for coherence, whenever setting up SurrealMCP for a new project,
      or when the user mentions "SurrealDB", "canonical layer", "client_access tagging",
      "affiliation edge", or names this skill directly. Encodes augment-it's live
      schema (persons/organizations/affiliations/observations/events) as the worked
      example, the per-table client_access shape (string[] on most tables, singular
      string on observations — a real inconsistency, not a typo), the flag-don't-fix
      verification discipline, and the read-only-vs-full-CRUD tradeoff of the official
      surrealmcp server. Generalizes past augment-it to any project (dididecks-ai,
      memopop-ai) that adopts the same schemaless-canonical-layer + observations-as-log
      pattern.
  skill_md_body_lines: 235
  missing_required_fields: []
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: skill-md-only
- name: theme-system
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/theme-system
  path_from_monorepo_root: context-v/skills/theme-system
  has_skill_md: true
  skill_md_frontmatter:
    name: theme-system
    description: The Lossless Group's theme and mode architecture — two-tier token
      system, three-mode contract (light/dark/vibrant), theme.css organization, and
      design system conventions. Use when setting up themes/modes for any Astro Knots
      site, debugging mode toggles, working with CSS tokens, or when the user mentions
      "vibrant mode", "two-tier tokens", "theme.css", or design system patterns.
  skill_md_body_lines: 90
  missing_required_fields: []
  asset_counts:
    references_md: 3
    templates_files: 0
    scripts_files: 0
    total_md: 4
  completeness: complete
- name: timeline-scenario-analysis
  source_repo_slug: lossless-monorepo
  skill_dir_path: /Users/mpstaton/code/lossless-monorepo/context-v/skills/timeline-scenario-analysis
  path_from_monorepo_root: context-v/skills/timeline-scenario-analysis
  has_skill_md: true
  skill_md_frontmatter:
    title: Timeline Scenario Analysis
    lede: 'Answers the second of the two foundational VC questions — *how fast can
      it get that big?* — by stress-testing the company''s current MoM/YoY growth
      at its actual unit of sale across four scenarios: sustain, improve, plateau,
      reduce. Operates on the penetration grid produced by the sibling skill [[market-capture-analysis]];
      sensitivity tables show what it takes to reach each cell and how time-to-base-case
      shifts with small growth-rate changes.'
    date_authored_initial_draft: 2026-06-09
    at_semantic_version: 0.0.0.1
    usage_index: 0
    publish: false
    category: Reference
    tags:
    - Timeline-Scenarios
    - Growth-Sensitivity
    - MoM-YoY
    - Investment-Memo
    - Synthesis
    authors:
    - Michael Staton
    augmented_with: Claude Code (Opus 4.7)
  skill_md_body_lines: 92
  missing_required_fields:
  - name
  - description
  asset_counts:
    references_md: 0
    templates_files: 0
    scripts_files: 0
    total_md: 1
  completeness: missing-required-fields
---

# Skills Manifest

Auto-generated inventory of agent skills (Anthropic agent-skills spec) found under any `context-v/skills/` directory in the curated sources. Tracked separately from `corpus-manifest.md` so skills don't pollute the fill-out to-do list — but indexed downstream alongside the corpus. Re-run `python scripts/build-skills-manifest.py` after editing skills or `sources.md`.

## Summary

- Total skills: **27**
- With `SKILL.md`: 24
- Without `SKILL.md`: 3

### By completeness

| state | count |
|---|---:|
| `complete` | 14 |
| `skill-md-only` | 6 |
| `missing-required-fields` | 4 |
| `no-skill-md` | 3 |

### By source repo

| source_repo_slug | count |
|---|---:|
| `lossless-monorepo` | 27 |

## Skills

| name | source | completeness | refs | templates | scripts | description |
|---|---|---|---:|---:|---:|---|
| [`astro-knots`](../../context-v/skills/astro-knots/SKILL.md) | `lossless-monorepo` | `complete` | 7 | 0 | 0 | The Lossless Group's Astro Knots conventions — vision, tech hierarchy, approved framewo… |
| [`changelog`](../../context-v/skills/changelog) | `lossless-monorepo` | `no-skill-md` | 0 | 0 | 0 |  |
| [`changelog-conventions`](../../context-v/skills/changelog-conventions/SKILL.md) | `lossless-monorepo` | `complete` | 5 | 2 | 0 | How The Lossless Group writes and structures changelog/ entries across all repos (proje… |
| [`chroma-agent-skills`](../../context-v/skills/chroma-agent-skills) | `lossless-monorepo` | `no-skill-md` | 0 | 0 | 4 |  |
| [`competitive-analysis`](../../context-v/skills/competitive-analysis/SKILL.md) | `lossless-monorepo` | `missing-required-fields` | 0 | 0 | 0 |  |
| [`context-vigilance`](../../context-v/skills/context-vigilance/SKILL.md) | `lossless-monorepo` | `complete` | 6 | 6 | 0 | Lossless Group's framework for managing context-v/ directories in any project. Use when… |
| [`crawl-fetch-ingest`](../../context-v/skills/crawl-fetch-ingest/SKILL.md) | `lossless-monorepo` | `complete` | 0 | 0 | 8 | The Lossless Group's workflow for filling in team and portfolio metadata for VC firms a… |
| [`decile-hub-connector`](../../context-v/skills/decile-hub-connector/SKILL.md) | `lossless-monorepo` | `complete` | 1 | 0 | 0 | How augment-it (and any Lossless VC-client workspace) talks to the Decile Hub API — the… |
| [`deck-iteration-workflow`](../../context-v/skills/deck-iteration-workflow/SKILL.md) | `lossless-monorepo` | `complete` | 1 | 2 | 0 | The Lossless Group's workflow for developing slides-only Astro sites for fundraise proc… |
| [`generate-consistent-og-images`](../../context-v/skills/generate-consistent-og-images/SKILL.md) | `lossless-monorepo` | `missing-required-fields` | 0 | 2 | 0 |  |
| [`gh-cli-projects-tasks-conventions`](../../context-v/skills/gh-cli-projects-tasks-conventions/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | How The Lossless Group uses the `gh project` CLI (GitHub Projects v2) to manage tasks a… |
| [`git-conventions`](../../context-v/skills/git-conventions/SKILL.md) | `lossless-monorepo` | `complete` | 3 | 0 | 0 | The Lossless Group's git commit message conventions — structured headers with action ve… |
| [`lossless-flavored-markdown`](../../context-v/skills/lossless-flavored-markdown/SKILL.md) | `lossless-monorepo` | `complete` | 5 | 0 | 0 | The Lossless Group's extended-markdown flavor — what LFM is, when to use it, how its di… |
| [`maintain-design-md`](../../context-v/skills/maintain-design-md/SKILL.md) | `lossless-monorepo` | `complete` | 0 | 1 | 0 | How to author and maintain a `DESIGN.md` file at the root of any Lossless project (site… |
| [`maintain-filemap`](../../context-v/skills/maintain-filemap/SKILL.md) | `lossless-monorepo` | `complete` | 0 | 0 | 1 | Use whenever the directory shape of a Lossless pseudomonorepo (or any child repo) chang… |
| [`maintain-splash-pages`](../../context-v/skills/maintain-splash-pages/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | The Lossless Group's pattern for repo-level splash pages — small Astro sites at <repo>/… |
| [`market-capture-analysis`](../../context-v/skills/market-capture-analysis/SKILL.md) | `lossless-monorepo` | `missing-required-fields` | 0 | 0 | 0 |  |
| [`open-graph-share-seo-geo`](../../context-v/skills/open-graph-share-seo-geo/SKILL.md) | `lossless-monorepo` | `complete` | 5 | 0 | 0 | How to make a page unfurl reliably in iMessage, WhatsApp, Slack, Discord, LinkedIn, and… |
| [`overlay-svg-text`](../../context-v/skills/overlay-svg-text/SKILL.md) | `lossless-monorepo` | `complete` | 0 | 2 | 0 | How to overlay on-brand SVG text on Lossless OG / share imagery — Hack Bold gradient-fi… |
| [`pseudomonorepos`](../../context-v/skills/pseudomonorepos/SKILL.md) | `lossless-monorepo` | `complete` | 6 | 0 | 0 | The Lossless Group's coined term and pattern — parent repos that aggregate child repos … |
| [`search-lossless-corpus`](../../context-v/skills/search-lossless-corpus/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | Use whenever the user asks a question that prior work might already have answered — "wh… |
| [`slide-target`](../../context-v/skills/slide-target/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | Load the full working context for ONE DidiDecks slide (deck/variant/slot) so an agent c… |
| [`splash`](../../context-v/skills/splash) | `lossless-monorepo` | `no-skill-md` | 0 | 0 | 0 |  |
| [`study-repos-first`](../../context-v/skills/study-repos-first/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | The Lossless Group's discipline of pinning a curated collection of upstream repos (a "s… |
| [`surrealdb-canonical-layer`](../../context-v/skills/surrealdb-canonical-layer/SKILL.md) | `lossless-monorepo` | `skill-md-only` | 0 | 0 | 0 | Verify a SurrealDB-backed canonical layer directly, over the `surrealdb` MCP server, in… |
| [`theme-system`](../../context-v/skills/theme-system/SKILL.md) | `lossless-monorepo` | `complete` | 3 | 0 | 0 | The Lossless Group's theme and mode architecture — two-tier token system, three-mode co… |
| [`timeline-scenario-analysis`](../../context-v/skills/timeline-scenario-analysis/SKILL.md) | `lossless-monorepo` | `missing-required-fields` | 0 | 0 | 0 |  |

