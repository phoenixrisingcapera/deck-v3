# Deck Processing Source Pipeline

This folder maps the active backend code that turns an uploaded deck source into
source slides, thumbnails, embedded assets, and miniature previews.

Do not move the source files into this folder. The Python modules stay in
`app/services/` and `app/workers/` so imports, worker entrypoints, and tests keep
working. This folder is the human-readable infrastructure map.

## Product Flow

```text
uploaded source file
  -> source_extraction worker
  -> deterministic PDF/PPTX structure extraction
  -> miniatures worker
  -> DB-persisted source previews
  -> smart_deck_context / db_publisher
  -> workflow-state canOpenSmartDeck=true
```

## Active Files

| File | Owns | Does not own |
| --- | --- | --- |
| `app/services/deck_extractors/pdf_image_extractor.py` | Extract embedded PDF images into deck-scoped source assets. | DB rows, workflow readiness, thumbnails. |
| `app/services/pdf_deck_extraction_service.py` | Build the deterministic in-memory PDF structure payload: metadata, text, OCR fallback, thumbnail asset references, embedded image assets. | Persisting `DeckSlide` rows. |
| `app/services/slide_thumbnail_service.py` | Render lightweight PDF page thumbnail artifact files for deterministic extraction. | DB source preview rows. |
| `app/services/deck_preview_service.py` | Persist source preview images into `DeckSlide` and `DeckSlideAsset` rows. | Embedded image extraction and final Smart Deck readiness unless explicitly requested. |
| `app/services/presentation_miniature_service.py` | Worker-stage adapter that validates PDF/PPT/PPTX source type and delegates preview persistence. | Rendering logic and direct workflow job claiming. |
| `tests/test_deck_preview_service.py` | Verifies DB-facing miniature preview persistence and readiness publication behavior. | Embedded image extraction details. |
| `tests/test_pdf_image_extractor.py` | Verifies embedded image extraction safety, storage paths, and idempotency. | DB preview persistence. |

## Contract Boundaries

### Embedded PDF Images

`pdf_image_extractor.py` returns typed asset dictionaries grouped by page number.
Those assets are attached to the extracted slide structure by
`pdf_deck_extraction_service.py`.

It must:

- validate the source path is a PDF
- use one engine for metadata and extraction
- store assets under the deck/upload prefix
- enforce image count and size limits
- return explicit extraction errors instead of silent failure

### PDF Structure Extraction

`pdf_deck_extraction_service.py` orchestrates deterministic extraction and returns
an in-memory payload. Persistence happens later through `deck_structure_service`.

It must:

- preserve page order
- keep text/OCR/image/thumbnail errors visible in `metadataJson.extractionErrors`
- attach thumbnails and embedded image assets to the extracted slide payload

### Thumbnails Versus Source Previews

There are two image paths by design:

- `slide_thumbnail_service.py` renders extraction thumbnails attached to the
  structure payload.
- `deck_preview_service.py` renders and persists canonical source previews in the
  database for workspace/UI use.

Do not collapse these until there is a shared renderer plus migration tests. They
serve different contracts.

### Miniatures Worker Readiness

`presentation_miniature_service.py` calls `extract_source_previews`.

The important flag is:

```python
publish_ready_state=False
```

Miniatures should create previews without opening Smart Deck. Later workflow
stages decide readiness.

## Verification

Run from `deck-backend-rescue`:

```bash
python3 -m compileall -q app tests/test_pdf_image_extractor.py tests/test_deck_preview_service.py
.venv/bin/python -m pytest tests/test_pdf_image_extractor.py tests/test_pdf_text_extractor.py tests/test_deck_preview_service.py -q
.venv/bin/python -m pytest tests/test_source_extraction_pipeline_contract.py tests/test_source_pipeline_optional_brand_contract.py -q
PYTHONPATH=. .venv/bin/python scripts/check_deck_extractor_runtime.py
```

## Prune Rules

Safe to prune:

- generated caches
- duplicate historical runbook fragments
- placeholder modules that are not imported and have no tests

Do not prune:

- any file in the active table above
- worker entrypoints still referenced by Railway/startup tests
- compatibility shims until imports are migrated
