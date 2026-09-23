$$ Lossless Flavored Markdown
# Everything flave renders today
&& One document that exercises every feature the renderer supports — so a regression is visible, not theoretical

This file is the demo **and** the manual test. If a feature stops working, you
see it here before a user does. Open `themes/lossless.css` in the Files rail and
change a value: everything below restyles as you type.[^a1b2c3]

---

## 1 · Inline

Prose carries **bold**, *emphasis*, `inline code`, ~~strikethrough~~, and
[links](https://lossless.group).

A `::` **leaf directive** is block-level — it owns its own line:

::badge{label="v0 shipped" tone="info"}

::badge{label="needs a browser drive" tone="warning"}

## 2 · Callouts, all four tones

Tone is semantic **state**, deliberately not the clearance ramp — clearance means
*who may see this*, and a warning makes no claim about visibility.[^d4e5f6]

> [!note] Info reads slate
> Used for note, tip, abstract, question, quote, example, success.

> [!warning] Warning reads amber
> Used for warning, caution, attention.

> [!danger] Danger reads vermilion
> Used for danger, error, bug, failure, missing.

> [!spaceship-status] Unknown types degrade, never disappear
> lfm accepts any `[A-Za-z0-9_-]+` as a callout type, so the vocabulary is open.
> This one has no tone mapping, so it falls back to neutral graphite and keeps
> its raw type on the element.

## 3 · Nesting — the load-bearing case

A container must recurse through the renderer. Stringify its children and
everything below quietly turns into text.

> [!warning] A table inside a callout
>
> | Surface | Status   | Milestone |
> |:--------|:--------:|----------:|
> | flow    | building |        M1 |
> | deck    | parked   |        M7 |
> | paged   | parked   |        M8 |
>
> Left, centre and right alignment all come from the table node, threaded down
> by column index.

> [!note] A fenced block inside a callout
>
> ```js
> const flave = 'a bundle of plain web-native files';
> ```

> [!note] A callout inside a callout
> > [!danger] Two levels deep
> > And still rendering as itself.

> [!note] A list inside a callout
> - nested lists work
>   - two levels
> - and ordered ones
>
> 1. first
> 2. second

## 4 · Task lists

- [x] Renderer ports the AstroMarkdown dispatch table
- [x] Trigger-packs render without touching the renderer
- [x] Callout and Table are real components
- [ ] Codified browser drive
- [ ] Folder picker

## 5 · Code

```css
/* Edit themes/lossless.css and this document restyles live. */
:root {
  --color-accent: #ff4d2e;
}
```

```bash
nix develop --command pnpm tauri dev
```

## 6 · Trigger-packs

A trigger-pack is a Svelte component plus one line of registration. The renderer
has never heard of `metric-card` — it hits an unrecognized directive, looks the
name up in a registry, and hands over the attributes.

:::metric-card{value="10,179" label="corpus chunks"}
:::

An **unregistered** directive still renders its content rather than vanishing:

:::not-registered
this prose survives
:::

## 7 · Quotes and rules

> A plain blockquote is not a callout. It has no type and no tone, and it should
> not acquire one by accident.

---

## 8 · Not wired up yet

Honest list — these are lfm features the editor does **not** enable today:

| Feature | Why not |
|:--------|:--------|
| Wikilinks | lfm gates them behind a per-site resolver; flave has not picked one |
| Code-fence formats (`yang`, `plantuml`, `json-schema`) | Opt-in, and `plantuml` imports a node builtin |
| Link previews / OG | Needs network access, which lands with the trust model |
| Image carousel | No `assets/` folder in the workspace yet |

[^a1b2c3]: [Phase 2 — The Workspace and the Files Surface](https://github.com/lossless-group/flave/blob/development/context-v/plans/Phase-2-The-Workspace-And-The-Files-Surface.md)
[^d4e5f6]: [flave DESIGN.md — callout tones are state](https://github.com/lossless-group/flave/blob/development/splash/DESIGN.md)
