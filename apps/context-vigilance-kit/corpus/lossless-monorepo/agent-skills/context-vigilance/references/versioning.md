---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/context-vigilance/references/versioning.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/context-vigilance/references/versioning.md"
---

# Lossless 4-Part Versioning

> **Field name:** the standard is **`at_semantic_version`** — it reads naturally as "this doc is *at* version X," and it's what ~4,140 files and every template use. Write that one.
>
> **`semantic_version` is a permanently-accepted alias** for the same property and the same value (~330 files). It is not a legacy spelling awaiting cleanup: **no migration is planned and none is wanted.** Resolving one extra key is free for a renderer; rewriting hundreds of files to unify the spelling buys nothing. Consumers read `at_semantic_version ?? semantic_version`.
>
> So: **write `at_`, read either, never rewrite a file just to change which name it uses.** Everything below applies identically to both.
>
> Bump it together with `date_authored_current_draft` — a version move and a substantive revision are the same event.

The version field in `context-v/` frontmatter uses **four** integers, not three:

```
epoch . major . minor . patch
  │       │       │       │
  │       │       │       └── typo, clarification, small wording fix
  │       │       └────────── new section, additive content
  │       └────────────────── restructure of the document
  └────────────────────────── total pivot — fundamentally different direction
```

## Starting version

New documents start at `0.0.0.1`.

## Epoch semantics

- **`0.x.x.x`** = proposal / not-yet-adopted. Doc exists but the team hasn't bought in.
- **`1.0.0.0`** = first accepted version. Promote a doc from epoch 0 to epoch 1 when it's been adopted as the way the project actually works.
- **`2.0.0.0`+** = total pivot. Not a restructure — a fundamentally different direction. Use when the previous epoch is being abandoned or replaced wholesale, not refined.

## When to bump which digit

| Change | Bump |
|---|---|
| Fix a typo, clarify a sentence, tighten wording | `patch` |
| Add a new section, add an example, append meaningful content | `minor` |
| Restructure sections, change the doc's organization, merge/split docs | `major` |
| Total pivot — the doc now argues for a fundamentally different approach | `epoch` |

## Cascading reset

Standard semver-style cascading is **encouraged but not enforced**:

- Bumping `minor` *should* reset `patch` to 0 (e.g., `0.0.1.5` → `0.0.2.0`)
- Bumping `major` *should* reset `minor` and `patch` (e.g., `0.0.2.5` → `0.1.0.0`)
- Bumping `epoch` *should* reset everything (e.g., `0.3.2.5` → `1.0.0.0`)

The team is ADHD-friendly about this. Don't block on it. Consistency within a single file is the real goal — if a file has been climbing without resets, keep climbing rather than retroactively fixing.

## When you can't decide

Bump the **patch**. Always safe. The worst outcome is under-signaling a change, which is better than blocking on the question.

## Don't decrement

Versions only go up. If you make a mistake, fix forward with a patch bump that explains the correction.

## Example progression

```
0.0.0.1   # initial proposal
0.0.0.2   # fixed a typo
0.0.1.0   # added "Decision Tree" section
0.0.1.1   # clarified one bullet in the new section
0.0.2.0   # added a second new section
0.1.0.0   # restructured into 3 parts instead of running prose
1.0.0.0   # team adopted it; promoted from proposal to canonical
1.0.0.1   # typo fix on the canonical version
2.0.0.0   # we abandoned this approach entirely; this doc now argues for the replacement
```

## What to do alongside the bump

Always update `date_modified` in the same edit.
