---
site_uuid: a124b762-4157-4d2f-9708-54ad2fbb864a
hex_code: gznuum
title: Continuous Integration with GitHub Actions
lede: Sixteen workflows across the tree and fourteen of them are deploys. We have
  automated shipping thoroughly and automated checking almost not at all — so every
  silent failure still gets caught by a person, in another repo, weeks later.
publish: true
date_created: 2026-08-17
date_modified: 2026-08-17
date_authored_initial_draft: 2026-08-17
date_authored_current_draft: 2026-08-17
authors:
- Michael Staton
augmented_with:
- Claude Code on Opus 5 (1M context)
at_semantic_version: 0.0.1.0
status: Draft
summary: The org-wide pattern for GitHub Actions CI. Load when adding CI to any repo
  in the tree, when a deploy workflow starts failing after a dependency or action
  bump, or when deciding what a workflow should actually verify. Encodes the verify/deploy
  split, the --ignore-workspace determinism rule, the monorepo hoisting trap that
  makes a green local build lie to you, action-version currency, and the run-it-locally-first
  discipline. Astro-specific application lives in the astro-knots sibling.
tags:
- Continuous-Integration
- GitHub-Actions
- Pseudomonorepos
- Testing
- Developer-Experience
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: blueprints/Continuous-Integration-with-GitHub-Actions.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/blueprints/Continuous-Integration-with-GitHub-Actions.md"
---

# Continuous Integration with GitHub Actions

## Why Care?

Take an inventory of the tree and the shape is stark. Sixteen workflows across sixteen repos, and **fourteen of them are deploys** — almost all the same `Deploy splash to GitHub Pages` job, replicated as the splash pattern spread. Two verify anything: `augment-it`'s `CI`, and `lfm`'s `Test the package`.

We automated shipping and did not automate checking.

That is not a small gap, because **the failures worth catching are the quiet ones.** A plugin that throws takes a build down and someone notices within the hour. A plugin that returns the *wrong shape* ships, renders slightly wrong on a site nobody looked at that day, and is discovered a fortnight later by a person who then has to bisect. Deploys catch the loud failures for free. Only tests catch the quiet ones.

## Deploying is not verifying, but it does some of the job

Worth saying because it changes what a new workflow needs to cover.

A deploy workflow that builds the site is already an integration test of everything the build touches. On `lfm`, `/demo` parses thirteen markdown fixtures through the real pipeline at build time, so a plugin that throws fails the Pages deploy today, with no test involved.

What it cannot see:

| Failure | Deploy | Tests |
|---|---|---|
| Something throws | ✅ | ✅ |
| Wrong value returned, no error | ❌ | ✅ |
| A public export quietly disappears | ❌ | ✅ |
| Two manifests drift out of agreement | ❌ | ✅ |
| A fixture stops demonstrating its feature | ❌ | ✅ |

So the two are complementary, and the split is the pattern:

- **`pages.yml`** (or equivalent) — *does it still build and ship?*
- **`test.yml`** — *does it still behave?*

Keep them separate workflows. They fail for different reasons, run at different speeds, and you want to read the answer to one without the other's noise.

## The shape

```yaml
name: Test the package

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

# A newer push to the same ref makes an in-flight run pointless.
concurrency:
  group: test-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read          # least privilege; deploys need more, tests do not

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: pnpm/action-setup@v6
        with: { version: 9 }
      - uses: actions/setup-node@v7
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile --ignore-workspace
      - run: pnpm exec tsc --noEmit
      - run: pnpm test
```

`workflow_dispatch` costs one line and means you can re-run without an empty commit. `pull_request` matters more than `push` — catching it before merge is the entire point.

## Always `--ignore-workspace`

**This is the rule most likely to bite in this tree specifically.**

Every repo here lives inside a parent pseudomonorepo, and many parents carry a `pnpm-workspace.yaml`. A plain `pnpm install` on a developer machine therefore resolves through the *parent* workspace and pulls in sibling projects. On a runner, only the one repo is checked out, so there is no parent — and the two installs are not the same install.

```bash
pnpm install --frozen-lockfile --ignore-workspace
```

Pass it everywhere, in every workflow, and pass it locally when you want to know what CI will see. Without it you are testing a dependency graph that exists on exactly one machine.

## The hoisting trap, which will cost you an afternoon

A build that passes locally and fails on the runner, with a resolve error for a package you can plainly see installed.

**Node resolves a bare import by walking up from the importing file.** So a file at `repo/src/parse.ts` importing `unified` looks in `repo/node_modules`, then `../node_modules`, and so on. It never looks in `repo/splash/node_modules`, no matter what `splash/package.json` declares.

Two consequences that took two failed deploys to separate on `lfm`:

1. **A nested project that compiles source from its parent inherits the parent's dependencies.** The splash imports `../../../src/index.ts`, so building the site means building the package, so the package's deps must be installed. The workflow needs *both* installs, root first.
2. **Declaring the dependency in the nested manifest does not fix it**, because the failing import is not in the nested project. It is in the parent's source, resolving from the parent's root.

Why it hid for so long: locally a developer always has both installed, so the nested project silently borrows from one directory up. It only surfaced when a `pnpm/action-setup` bump installed a newer pnpm that hoists less.

**How to actually reproduce it before pushing:**

```bash
mv node_modules .node_modules_hidden     # remove what CI does not have
cd splash && pnpm build                   # now it fails the way the runner fails
cd .. && mv .node_modules_hidden node_modules
```

A "clean install" that leaves the parent's `node_modules` in place is not clean. It is the exact configuration that hides the bug.

## Keep the actions current, and know they move fast

GitHub deprecated the Node 20 runtime; actions still targeting it get forced onto Node 24 with a warning on every run. The versions drift further than the warning implies — as of August 2026:

| Action | Common in this tree | Current |
|---|---|---|
| `actions/checkout` | v4 | **v7** |
| `actions/setup-node` | v4 | **v7** |
| `pnpm/action-setup` | v4 | **v6** |
| `actions/configure-pages` | v5 | v6 |
| `actions/upload-pages-artifact` | v3 | v5 |
| `actions/deploy-pages` | v4 | v5 |

Check current majors rather than trusting a memory of them:

```bash
for r in actions/checkout actions/setup-node pnpm/action-setup; do
  echo "$r $(gh api repos/$r/releases/latest --jq .tag_name)"
done
```

**Bump the three general actions freely; treat the Pages trio as one unit.** `configure-pages`, `upload-pages-artifact` and `deploy-pages` have to move together and they act on a live site, so that is its own change with its own verification — not a rider on an unrelated commit.

Better still, stop checking by hand — see Dependabot below.

And expect a bump to expose something. The `v4 → v6` pnpm bump above did not break the deploy; it removed the hoisting that had been hiding a real missing dependency for months. That is a bump doing its job.

### Do not rely on remembering — let Dependabot do it

Everything above is a discipline, and disciplines decay. The section you are reading exists because a workflow written *yesterday* shipped on `actions/checkout@v4`: it was copied from an older sibling file, and nothing about authoring a workflow prompts you to check whether the version you typed is current.

Ten lines removes the need to remember:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: monthly
    commit-message:
      prefix: ci
    labels: [ci]
    open-pull-requests-limit: 3
```

It costs no CI minutes of its own — the PR it opens runs the normal workflows, which is precisely the verification a version bump wants.

**Monthly, not weekly.** These actions cut a major roughly once a year. Across sixteen repos a weekly cadence is pure noise, and a bot that gets ignored is worse than no bot, because it looks like coverage while nobody reads it.

**Enable `github-actions` and stop there, at least at first.** The npm ecosystem on a content repo produces a lot of lockfile churn that wants a human deciding when. For the security case specifically, a scheduled `pnpm audit` (as `site/` runs weekly) covers the part that genuinely must be automatic.

As of writing, **no repo in the tree has a `dependabot.yml`**, which is why the same three stale actions appear in all fourteen splash-deploy workflows. Dropping this file into each is the cheapest way to make the fix stick everywhere rather than in whichever repo someone touched last.

## Publishing repos get a dry run

For anything published to JSR or npm, add a second job:

```yaml
  publishable:
    runs-on: ubuntu-latest
    steps:
      # … checkout / pnpm / node / install …
      - run: pnpx jsr publish --dry-run --allow-dirty
```

It catches two things invisible until the moment you publish, both of which have bitten `lfm` once each: a slow-types error in the public API, and an entrypoint declared in `deno.json` that does not resolve. A test can assert the manifests agree; only the dry run proves the registry accepts the result.

## Run every command locally first

Obvious, routinely skipped, and the reason a first CI commit usually lands red.

Before pushing a workflow, run each `run:` line by hand in the order the job will run them. If a step needs the runner's environment to pass, that is worth knowing before it is worth debugging through a thirty-second feedback loop.

## Non-blocking jobs are allowed

`augment-it` runs a design-drift check as `pnpm design:drift || true` — it reports without failing the build. Legitimate for a signal you want visible but not yet enforced. Use it for checks that are aspirational or noisy, and remove the `|| true` when the signal is trustworthy. Do not use it to silence a check that is telling the truth.

## Adding CI to a repo that has none

1. Confirm there is something to run. `pnpm test` that does nothing is worse than no workflow, because it is a green check that means nothing.
2. Copy the shape above. Adjust `node-version` and the install flags to the repo.
3. Run every command locally, including with the parent `node_modules` hidden if anything nested compiles source from a parent.
4. Push, then **watch the run and read the log** — confirm the assertion count, not just the checkmark. A suite that silently ran zero tests reports success.
5. If it goes red, the failure is information about the repo, not a reason to weaken the workflow.

## See also

- `astro-knots/context-v/blueprints/Continuous-Integration-for-Astro-Knots-Sites.md` — this pattern applied to the Astro sites, where the deploy workflow is the common case
- `lfm/.github/workflows/test.yml` — the reference implementation, with the jsr dry-run job
- `ai-labs/augment-it/.github/workflows/ci.yml` — the prior art: matrix builds, per-service test groups, a non-blocking drift check
- [[Maintain-a-Github-Splash-Page-for-each-Repo]] — where the fourteen deploy workflows came from
