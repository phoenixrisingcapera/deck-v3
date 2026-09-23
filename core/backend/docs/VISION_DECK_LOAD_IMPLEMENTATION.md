# Vision Deck Load Implementation

The source-preview critical path uses concurrent PyMuPDF rendering with
progressive database commits. It does not wait for an LLM call.

## Runtime

- `DECK_PREVIEW_PARALLELISM=4` controls concurrent page rendering (`1` to `16`).
- Preview objects use
  `users/{userId}/decks/{deckId}/previews/slide-{number}-{previewId}.png`.
- `DeckSlide` owns extracted text/title/order.
- `DeckSlideAsset(asset_type="source_preview")` owns preview metadata.
- Workflow state maps previews to authenticated `/api/decks/.../preview` URLs.
- Qwen vision receives stored image bytes as data URLs, not app-relative paths.
- `qwen3.7-plus` supports multimodal document analysis; the configured
  `qwen-vl-ocr-2025-11-20` route is used for OCR-specific vision calls.

See the workspace-root `VISION_DECK_LOAD_IMPLEMENTATION.md` for the complete
two-database plan, surface status, acceptance tests, and official model links.

## Verification

```bash
python -m pytest -q \
  tests/test_deck_preview_service.py \
  tests/test_qwen_structured_json_and_vision.py \
  tests/test_smart_edit_workflow_routes.py \
  tests/test_due_diligence_api_contract.py \
  tests/test_smart_deck_render_schema.py
```

Local tests prove prompt/transport/schema/persistence contracts. A real
`QWEN_API_KEY`, deployed object storage, and authenticated deck are required to
prove provider latency and end-to-end production behavior.
