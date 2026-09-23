# Kopie processing diagnosis — 8 September 2026

Railway project: `af0ad057-2bac-4a20-84d4-92999008271c`, production environment
`62b96a38-4f13-49d6-8a9e-64f664f8abc8`.
Uploaded deck: `deck_f47c338758056655`.

## Observed production failure

- Upload completion returned HTTP 200 at 12:29:34 UTC.
- Five worker preparation jobs completed between 12:29:43 and 12:30:59 UTC.
- The worker logged an OpenAI request at 12:31:29 UTC and a successful API call
  at 12:36:21 UTC. A successful API response does not establish valid deck output.
- Immediately afterward, generation failed at `start_provider_attempt` with
  `InstantOperationBudgetExceeded: Instant Deck provider request-start budget is exhausted.`
- The generation loop retries after `HtmlDeckCompileError`, but the upload
  worker set `operation.max_provider_request_starts = 1`. The shared generation
  policy permits two starts: initial generation and one validation retry.

This conflicting limit explains why the validation retry could not start.
The precise compiler rejection of the first response is not present in the
retrieved logs. It is saved in the provider attempt's `validation_summary_json`;
reading that row remains necessary to identify the original invalid-output issue.
SSH access lacks a registered key, and neither database exposes a public
connection URL. No infrastructure or credentials were changed to gain access.

## Local checks

Input: repository-root `Kopie.pdf`, 39,927,436 bytes, 14 pages, unencrypted.

- Actual `extract_pdf_deck_structure` completed in approximately 3.6 seconds.
- Extracted 25 embedded image references; 13 pages contained native text.
- Page 4 has no native text. Local OCR could not run because Tesseract is absent.
  The production Dockerfile includes `tesseract-ocr`; this local limitation does
  not establish a production OCR failure.
- Actual source-preview rendering produced all 14 nonempty PNGs, 2880 × 1620.
- Regression test failed on the original worker with `assert 1 == 2`.
- After correction, 24 targeted tests passed: upload provider budget, command
  idempotency, worker policy, art-direction contract, and HTML compiler contract.

Tests used the existing sibling backend virtual environment, importing this
checkout's application code, with `APP_ENV=test` and `DATABASE_URL=sqlite://`.
Extraction and preview outputs are under `/tmp/kopie-local-assets`; extracted
structure is `/tmp/kopie-extraction.json`. No paid provider calls were made locally.

## Local correction and remaining verification

The upload worker now uses `MAX_PROVIDER_REQUEST_STARTS` for both persisted
configuration and its locked precharge eligibility check. The regression test
executes the worker preparation path, permits two recorded provider starts,
and verifies rejection of a third. The cumulative $5 cost guard is unchanged.

This correction is not deployed. It does not repair an already failed operation
or prove that a second generated response will pass compilation. Before declaring
the product fixed, inspect the saved validation issues, deploy the correction,
and verify an authorized upload-to-generation-to-render journey on Railway.
