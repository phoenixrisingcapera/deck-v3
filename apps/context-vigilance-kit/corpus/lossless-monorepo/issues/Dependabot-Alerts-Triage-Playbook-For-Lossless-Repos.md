---
title: Dependabot Alerts — Triage Playbook for Lossless Repos
lede: The bulk-dismiss script with categorized rationales cleared 86 Dependabot alerts
  across three Obsidian plugins in about five minutes.
date_created: 2026-05-17
date_modified: 2026-05-17
status: Reference / Playbook
authors:
- Michael Staton
augmented_with:
- Claude Code on Claude Opus 4.7 (1M context)
tags:
- Dependabot
- Security-Alerts
- GitHub-API
- Triage-Playbook
- Obsidian-Plugins
- JS-Toolchain
- Dev-Tool-Transitives
applies_to:
- All lossless-group/* repos with a JS/TS lockfile
- Especially: Obsidian plugins (cite-wide, image-gin, perplexed-plugin, future siblings)
- Generally: Any pseudomonorepo child whose user-facing artifact is a bundled file
    (Astro sites, plugins, CLI tools)
site_uuid: 9f9a101f-1fa8-41b1-a0cc-3dcc9dd88939
hex_code: y1p8hs
date_authored_initial_draft: 2026-05-17
date_authored_current_draft: 2026-05-17
publish: true
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: issues/Dependabot-Alerts-Triage-Playbook-For-Lossless-Repos.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/issues/Dependabot-Alerts-Triage-Playbook-For-Lossless-Repos.md"
---

## Why This Exists

Every time we push to a Lossless repo that has Dependabot alerts enabled, the push output includes a line like `GitHub found 30 vulnerabilities on lossless-group/cite-wide's default branch (17 high, 9 moderate, 4 low). To find out more, visit:` and a link to the security dashboard. The dashboard shows a wall of CVE-coded entries with phrases like "ReDoS via crafted glob patterns," "prototype pollution in merge," "request.protocol spoofable via X-Forwarded-Proto from untrusted connections" — none of which tells you, the actual maintainer, whether any of it matters for your specific code.

We've ignored this signal for months across the family because nothing about it has been actionable on its face. That's the wrong response — Dependabot is doing legitimate vulnerability tracking, but the UI doesn't surface the one piece of information that determines whether to act: **is the vulnerable code path reachable from what ships to users?**

This doc codifies the answer for our typical repo shape so we don't re-derive it every six weeks.

## The Three Buckets

In every Lossless repo we've audited (cite-wide, image-gin, perplexed-plugin, and we expect: any astro-knots site, any tidyverse plugin, etc.), open alerts fall into three buckets:

### Bucket A — Stale: package was removed but alerts persist

Packages that used to be in `package.json` got removed in some prior cleanup commit, but Dependabot's alerts from before the removal stay open until GitHub's next scan re-runs against the new lockfile. The scan doesn't trigger reliably, especially when the removal happened on a long-lived feature branch that only landed on the default branch much later.

Typical packages in this bucket for the plugin family: `fastify`, `@modelcontextprotocol/sdk`, `body-parser`, `qs`, `path-to-regexp` — leftover from the starter-template fork lineage. None of these were ever used by any plugin code; they came in via the original `obsidian-sample-plugin` starter we forked from.

Dismissal reason: **`not_used`**.

### Bucket B — Already-fixed: lockfile is at or above `first_patched_version`

The package is still in the lockfile, but at a version equal to or greater than the alert's `first_patched_version`. GitHub's alert state hasn't caught up. Example we found: `fast-uri@3.1.2` in image-gin and perplexed, with two open alerts whose vulnerable range was `<=3.1.1` and `<=3.1.0` respectively — both fixed at the locked version, alert state stale.

Dismissal reason: **`tolerable_risk`** (with comment noting current pinned version exceeds fixed_in).

### Bucket C — Dev-toolchain transitive: real CVE, but not user-reachable

The package is in the lockfile at a vulnerable version, and is genuinely vulnerable to the named attack — BUT the package is a transitive dependency of a dev tool (ESLint, TypeScript, esbuild) that only runs at build/lint time on the developer's machine. It never ends up in the artifact that ships to users.

For Obsidian plugins specifically: the user-facing artifact is `main.js` produced by esbuild. esbuild externalizes Obsidian APIs and only bundles your own source. Dev-tool transitives (`minimatch`, `picomatch`, `brace-expansion`, `flatted`, `ajv`, `js-yaml`, `@eslint/plugin-kit`, etc.) don't make it into `main.js`. Exploiting them would require attacker-controlled input flowing through ESLint's config-parsing path or TypeScript's glob matching during local `pnpm build` — a threat model that maps to "someone slips a malicious-glob pattern into a PR that triggers ReDoS when you run `pnpm lint` locally." Theoretical, low impact, and not what end users are exposed to.

For Astro sites the same logic applies if the user-facing artifact is the built static output. For CLI tools the bundle decides. The rule is: **figure out which file(s) get distributed; check whether the vulnerable package code ends up in those files.**

Dismissal reason: **`tolerable_risk`**.

## Diagnostic Playbook

Before deciding whether to fix-vs-dismiss-vs-ignore an alert, run these three steps. They take ~30 seconds per alert.

### 1. List the open alerts with the data you need

```bash
gh api "/repos/lossless-group/<repo>/dependabot/alerts?state=open&per_page=50" \
  --jq '.[] | {n: .number, sev: .security_advisory.severity, pkg: .dependency.package.name, vuln_range: .security_vulnerability.vulnerable_version_range, fixed_in: .security_vulnerability.first_patched_version.identifier}'
```

This gives you the alert number, severity, package name, the vulnerable version range, and the version that patches it. That's the only data the dismissal logic needs.

### 2. Check whether the package is even in the lockfile

```bash
/usr/bin/grep -nE "<pkg>@" pnpm-lock.yaml
```

If zero hits → **Bucket A** (the package was removed; alert is stale). Dismiss as `not_used`.

(Note: `grep` is wrapped by Claude Code's shell to call `ugrep` — use `/usr/bin/grep` directly for unambiguous behavior inside scripts and `for` loops.)

### 3. If present, compare locked version vs `fixed_in`

The grep output shows the version line, e.g. `fast-uri@3.1.2:`. If `3.1.2 >= fixed_in (3.1.2)` → **Bucket B**. Dismiss as `tolerable_risk` with comment noting the version is already at or above the fix.

If `locked < fixed_in` → real exposure within the package itself. Now answer:

> *Does this code path ship to users?*

For our repo shapes the answer is almost always "no" because the package is a dev-tool transitive — **Bucket C**. Dismiss as `tolerable_risk` with the dev-toolchain comment.

If genuinely yes (the package is a runtime dep your `main.ts` actually imports) → **do not dismiss; bump the version**. `grep -r "from '<pkg>'" src/ main.ts` confirms whether it's imported. We have not yet encountered a real Bucket D in the plugin family.

## Bulk-Dismiss Script

Once you've confirmed every alert maps to one of the three buckets — and **only then** — you can mass-dismiss with this script. It iterates alerts per repo, picks a dismissal reason + comment per package, and PATCHes.

```bash
SHORT_COMMENT="Dev-toolchain transitive (ESLint/TypeScript/esbuild). Not bundled into shipped main.js. Exploitable only during local pnpm build with attacker-controlled input on a dev machine, never reachable in the installed Obsidian plugin."

for repo in cite-wide image-gin perplexed-plugin; do
  gh api "/repos/lossless-group/$repo/dependabot/alerts?state=open&per_page=50" \
    --jq '.[] | "\(.number)\t\(.dependency.package.name)"' > /tmp/alerts.tsv
  while IFS=$'\t' read num pkg; do
    case "$pkg" in
      fastify|"@modelcontextprotocol/sdk"|body-parser|qs|path-to-regexp)
        reason="not_used"
        comment="Direct dep removed from package.json; lockfile no longer references this package. Stale alert pending next Dependabot scan."
        ;;
      fast-uri)
        reason="tolerable_risk"
        comment="Lockfile already pins fast-uri at fixed version 3.1.2 (vulnerable range was <=3.1.1). Alert is stale; package is at the patched version."
        ;;
      *)
        reason="tolerable_risk"
        comment="$SHORT_COMMENT"
        ;;
    esac
    gh api -X PATCH "/repos/lossless-group/$repo/dependabot/alerts/$num" \
      -f state=dismissed -f dismissed_reason="$reason" -f dismissed_comment="$comment"
  done < /tmp/alerts.tsv
done
```

**Customize the package list** for non-Obsidian repos:

- For Astro sites: bucket A is empty (no fastify residue); bucket C swaps in Astro's own toolchain transitives (`vite`, `rollup`, etc.).
- For CLI tools: bundle target decides; if you bundle with esbuild, same logic; if you don't bundle (publish raw source), more packages reach the user.
- For TypeScript libs published to JSR/npm: this discipline changes — transitives of compile-time tools don't ship, but transitives of runtime deps DO ship to library consumers, so the dev-tool dismissal rationale doesn't transfer.

## API Gotchas We Hit

- **`dismissed_comment` is capped at 280 characters.** Comments longer than that return `422 Invalid request: Only 280 characters are allowed; N were supplied`. Test with `echo ${#VAR}` before running the loop. Our working comment was 227 chars after compression.
- **Valid `dismissed_reason` enum values:** `fix_started`, `inaccurate`, `no_bandwidth`, `not_used`, `tolerable_risk`. No `superseded`, no `already_fixed` — use `tolerable_risk` for the already-patched case and put the explanation in the comment.
- **Dismissals are fully reversible.** `gh api -X PATCH .../alerts/N -f state=open` reopens the alert. The action only touches GitHub's alert-state UI; nothing about your lockfile or code is changed.
- **GitHub classifies every alert with `scope: runtime`** based on lockfile presence, regardless of whether the package actually runs at runtime. Don't trust the `scope` field — verify with `grep -r "from '<pkg>'" src/ main.ts`.
- **`dependabot_security_updates` is the auto-PR-fix feature, not the alerts feature.** It's disabled on our repos per `gh api /repos/<o>/<r> --jq '.security_and_analysis'`. The alerts feature is separate and stays on. Don't conflate them.
- **The grep wrapper:** in Claude Code's shell, `grep` is overridden to call `ugrep` for repo-aware ignoring. Inside `for` loops and subshells the override sometimes loses tty context and fails with `command not found: grep`. Workaround: call `/usr/bin/grep` explicitly.

## When Alerts Reappear

Dismissals are per-alert (per-CVE-per-repo), not per-package. A future CVE filed against `minimatch` will surface as a new alert with a new number, no relationship to the ones we dismissed. That's correct behavior. Re-run the same script with the package added to the appropriate `case` arm.

When new repos get added to the family, run the script against them too once they accumulate alerts. The buckets transfer; the dismissal rationales transfer.

## What We Don't Recommend

- **Aggressive `pnpm.overrides`** as a long-term Dependabot-shutup strategy. We tried this for ajv/js-yaml/minimatch/flatted in cite-wide back in May; it covered the v3 alerts but missed the v9 alerts when those came out, and pnpm.overrides becomes a maintenance burden of CVE-tracking that produces no actual security improvement for an Obsidian plugin. Use overrides only when there's a real reason to constrain a transitive version (build correctness, behavior compatibility), not as a security-theater move.
- **Disabling Dependabot entirely** via repo settings. We want the alerts — they're useful for real runtime deps we haven't audited yet. We just want them dismissed for the buckets we've already triaged.
- **Auto-bumping dev deps to latest** because Dependabot flagged a transitive. ESLint 9→10, TypeScript 5→6, etc. each carry behavior changes that are unrelated to the CVE and produce far more incidental work than the CVE itself merits.

## Historical Resolution Snapshot

| Date | Repo | Alerts dismissed | Buckets |
|---|---|---|---|
| 2026-05-17 | `lossless-group/cite-wide` | 30 | A: 14, B: 0, C: 16 |
| 2026-05-17 | `lossless-group/image-gin` | 29 | A: 12, B: 2, C: 15 |
| 2026-05-17 | `lossless-group/perplexed-plugin` | 27 | A: 10, B: 0, C: 17 |
| | **Total** | **86** | — |

Final state across the family: **0 open alerts**. Each dismissed alert has a category + rationale visible in its respective `Security → Dependabot alerts → Dismissed` view.

## See Also

- `content-farm/CLAUDE.md` — plugin-family agent instructions (mentions ChromaDB-RAG corpus but not Dependabot triage; if this playbook gets used recurrently, consider adding a one-line backstop reference)
- `~/.claude/projects/-Users-mpstaton-code-lossless-monorepo-content-farm/memory/reference_dependabot_triage_playbook.md` — the per-content-farm-project memory entry of the same playbook (created in the same 2026-05-17 session so future Claude sessions in the plugin family can recall it)
- GitHub API docs: https://docs.github.com/en/rest/dependabot/alerts (for the full alert schema and the dismissal endpoint's parameter constraints)
