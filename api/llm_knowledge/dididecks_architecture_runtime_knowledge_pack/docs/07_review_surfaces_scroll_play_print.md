# Surface-Aware Review Model

Scroll-UI and Play-UI are coordinated implementations, not the same implementation rendered twice.

## Shared identity

```txt
slide id
slide key
deck id
variant key
shared deck data
```

## Surface-specific renderings

- Scroll: responsive, reading-oriented, long-form review
- Play: 16:9, presentation-oriented, keyboard/chrome interactions
- Print: export-safe, browser/PDF path
- Thumbnail: compact preview
- Editor: interactive block selection and editing

## Review matrix

Rows:

```txt
slides / slots
```

Columns:

```txt
variants
```

Cell content:

```txt
surface status: scroll, play, print, thumbnail
```

## Avoid vacuous ready

A variant cannot be marked ready if it has zero slides or zero required blocks.
