# flave

> **A document that keeps its workings.**
>
> Publish it and people see the conclusion. Send the file itself and they get the evidence, the data and its sources, the reasoning, and the design vocabulary that produced it — written in the languages agents already speak fluently, so a human and an agent can co-author inside it.

`.flave` is a document format. **flave** is the editor over it. Both are built on [Lossless Flavored Markdown](https://jsr.io/@lossless-group/lfm).

**Status: pre-implementation.** The master spec lives at [`context-v/specs/Master-Flave-An-Agent-Native-Document-Format-and-Publisher.md`](./context-v/specs/Master-Flave-An-Agent-Native-Document-Format-and-Publisher.md). Nothing is built yet.

---

## Why

Every incumbent document format was designed for a world where the only author was a human with a mouse. The format could be opaque because the only program that ever needed to read it was the program that wrote it.

That assumption is now false, and agents are bad at all of them — OOXML round-trips destroy formatting, `.key` and `.pages` are effectively closed, and a PDF is write-only. Meanwhile the substrate agents are *outstanding* at — HTML, CSS, SVG, JSON, the declarative chart grammars — is exactly what a modern document needs.

But the sharper reason is about labor, not legibility:

> Extensible authoring was always a good idea and always developer-only. Defining a new markdown syntax meant writing a `remark` plugin — an afternoon, plus a mental model most authors will never acquire. **That cost, not the concept, is why every author outside engineering lives inside a fixed set of block types someone else chose.**
>
> Writing a trigger definition and its template and CSS is now a thirty-second agent task. The barrier was labor, and the labor is gone.

Nobody has yet built the editor that assumes this.

## The core: internals vs. publication

The differentiator isn't surgical editing or durable identity. It's that **the document carries more than it shows, and the surplus is the valuable part.**

A `.flave` holds **content, data, and assets** — prose and transcripts, rows with their provenance, images with their licensing. Each carries a **clearance** (`private` → `team` → `lp` → `public`) and a **register** (`verbatim` / `full` / `brief`). An *audience* is a point on both axes, so one document yields your private notes, the team version, the LP version, and a punchy public one-pager — **and they don't drift.**

Clearance is monotonic and machine-checkable, which is what makes the promise provable rather than merely intended: nothing above `public` may appear in the public artifact, and the publish step fails if it does.

## Build order

Most of the master spec is **designed and parked**. The build order is deliberately small:

**v0 — the editor.** A markdown editor where you choose how it renders, define your own syntax triggers, and see the output live as you type. CodeMirror 6, `lfm` for parsing, a Svelte renderer ported from `AstroMarkdown.astro`, one hand-edited `theme.css`. No Tauri, no frames, no themes-as-packages, no embedded agent — you run Claude Code beside it and it writes trigger components into the project.

**v1 — clearance and audiences.** Block-level clearance, named audiences, `flave publish --audience`, and the scan that proves nothing leaked. Small once v0 exists.

**Parked:** the layout and frame system, `deck` and `paged` surfaces, the theme registry, Jujutsu integration, DuckDB and `sql` fences, figures, HTMX. All designed in the spec; none scheduled.

## Repository layout

| Path | Purpose |
|---|---|
| `context-v/` | Living documentation — the master spec, plus plans, blueprints, explorations as they appear |
| `changelog/` | Ship log, per the Lossless changelog conventions |
| `splash/` | GitHub Pages splash (placeholder — see its README) |

## Relationship to the rest of the tree

- **[`lfm`](https://github.com/lossless-group/lossless-flavored-markdown-package)** — a direct dependency, never forked. LFM owns parsing and trigger normalization; flave is a new renderer over the same AST.
- **`astro-knots/packages/lfm-astro`** — the Astro renderer. `AstroMarkdown.astro` is the reference `@flave/render` is ported from. Two renderers over one AST is LFM's design working as intended.
- **`ai-labs/augment-it`** and **`ai-labs/memopop-ai`** — flave is a *sibling*, not a substrate for either. Their chat surface and Tauri shell are ports of record for later milestones.

## License

TBD.
