# Editor Runtime Integration

The editor should render:

```txt
Deck → active slide → active variant → blocks
```

A selected block should reveal:

- block id
- block key
- block type
- slide title
- variant key
- content summary
- style summary
- position summary
- locked/generated status
- persistent field binding
- field usage count
- links to Smart Edit, Deck Map, and Rebuild

## Required block data attributes

Each rendered block should expose:

```txt
data-block-id
data-field-key, when bound
```

## Field-bound block warning

Use this exact warning:

> This block is linked to a persistent field. Editing the field can update other slides.

## Workflow links

```txt
/decks/[deckId]/smart-edit?field={fieldKey}&slide={slideId}&block={blockId}
/decks/[deckId]/map?field={fieldKey}
/decks/[deckId]/rebuild?field={fieldKey}
```
