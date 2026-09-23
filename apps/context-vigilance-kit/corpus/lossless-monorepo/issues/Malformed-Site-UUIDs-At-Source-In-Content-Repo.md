---
site_uuid: a9a201e1-e61a-4706-bf8a-1e1d79e22fb3
hex_code: lkd6pa
title: Malformed site_uuids at source in the content repo
lede: Six `content/` documents carry site_uuids with non-hex characters — an agent
  typed a plausible string instead of calling a generator.
summary: Records six invalid `site_uuid` values whose source files live in `content/`,
  outside the scope of the 2026-08-17 context-v frontmatter sweep. Includes the exact
  values, the offending characters, the source paths, and why roll-up regeneration
  cannot fix them. Also records the three false-positive classes a naive scan produces,
  so the next person does not re-derive them. Fix requires editing `content/` directly.
status: Open
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
tags:
- Issue
- Site-UUID
- Content-Repo
- Frontmatter
- Data-Integrity
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: issues/Malformed-Site-UUIDs-At-Source-In-Content-Repo.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/issues/Malformed-Site-UUIDs-At-Source-In-Content-Repo.md"
---

# Malformed site_uuids at source in the content repo

## Why this is written down rather than fixed

Found during the 2026-08-17 `context-v/` frontmatter sweep. The sweep's scope was
`context-v/` directories; `content/` is explicitly out of bounds and was never
touched. These are recorded so the finding survives the session.

**Roll-up regeneration will not fix them.** A roll-up copies frontmatter
faithfully, so every regeneration re-propagates the bad value into
`site/src/generated-content/` and `ai-labs/context-vigilance-kit/corpus/`. The
only fix is at source, in `content/`.

## The six

Each contains at least one character that is not a hex digit, so none will parse
as a UUID in any strict consumer. **Offending characters bolded in the notes.**

| Value | Bad chars | Source |
|---|---|---|
| `a0354223-396h-4rb4-a6ca-97afbe5cff17` | `h`, `r` | `content/lost-in-public/market-maps/Agentic AI in Medicine.md` |
| `y8f59v34-aa5b-4f79-b8a7-93c3fc99a89f` | `y`, `v` | `content/projects/Content-Farm/Specs/Implement-a-Vault-Wide-Citations-Manager.md` |
| `aad9a307-5897-418b-a822-f02gdbf6cb48` | `g` | `content/specs/Screencast-Diary-Capture.md` |
| `a2g8f7c3-3d19-4f05-267f-b5eb837f5f05` | `g` | `content/lost-in-public/issue-resolution/Nested-Scroll-and-Keyboard-Behavior-Conflicts.md` |
| `5716v092-c931-4c4d-88e1-188ec13b1a9d` | `v` | `content/lost-in-public/prompts/render-logic/Integrate-Collection-into-Site.md` |
| `6e6fbt60-22b9-4070-871d-972b3554a7c0` | `t` | `content/tooling/AI-Toolkit/Knowledge AI/Enjo AI.md` |

Four of these are already quoted in
`context-v/agent-skills/context-vigilance/references/frontmatter-spec.md` as the worked
example of why an agent must shell out for identifiers. **They were documented as
a cautionary tale and never actually repaired.**

## One more, probably fine

`content/lost-in-public/reminders/Specification-Guidelines-Template.md` carries
`site_uuid: {{generate-uuid}}`. It is a **template**, so an unfilled placeholder
is arguably correct content. Worth confirming nobody is copying the template
without filling it — but do not "fix" it reflexively.

## The fix

Per the spec, generate — never type:

```bash
uuidgen | tr 'A-Z' 'a-z'
```

**Do not reuse a value that already exists elsewhere.** Collect the registry
first and assert it is non-empty before trusting it:

```bash
rg -o --no-filename -g '*.md' -g '!node_modules' '^site_uuid:\s*(\S+)' -r '$1' . | sort -u
```

Then regenerate the roll-ups so the derived copies pick up the corrected values.

## Three false positives — do not chase these

A naive scan reports far more than six. All three classes were hit and dismissed
on 2026-08-17; re-deriving them costs an hour.

1. **Body code samples.** Grepping `^site_uuid:` across a whole file matches
   fenced examples in prose. `Enhanced-Filesystem-Observer-with-Prompts-Support.md`
   has a valid uuid at line 16 and *illustrative* bad ones at lines 534 and 746 —
   it is a document **about** frontmatter handling. **Only scan inside the leading
   `---` block.**
2. **The RFC example UUID.** `550e8400-e29b-41d4-a716-446655440000` is the
   canonical example from the UUID specification. It appears only in body examples.
3. **Trailing comments.** `context-v/agent-skills/*/templates/*.md` carry valid uuids
   followed by `# REGENERATE: uuidgen | …`. A regex capturing to end-of-line reads
   the comment as part of the value.

## Related

- `context-v/agent-skills/context-vigilance/references/frontmatter-spec.md` — the
  identity spec, including the generate-never-type rule and the base36 rationale
- [[Frontmatter-Normalization-The-Context-V-Tier]] — the sweep that found these
- **Roll-up rebuild.** The roll-up is likely to be rebuilt from GitHub CMS / CDN
  endpoints so content reaches the website and splash pages directly. Whatever
  replaces the current script inherits this problem: it must not treat a
  syntactically invalid identifier as a usable key.
