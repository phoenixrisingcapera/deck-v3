# Canonical Instant Deck production release — 2026-09-08

> Local update, 2026-09-09: all four browser/provider/render/publication/export
> canaries passed locally. The general-presentation follow-up awaits exact-SHA
> authorization; it has not been deployed. See [local-canary-release-review.md](local-canary-release-review.md)
> for acceptance, checks, costs and rollout/rollback steps. The production failure
> and deployed identities below remain historical online evidence.

Status: reviewed commit deployed to all five services; 7-page live acceptance FAILED.
The sequence stopped after one new operation and exactly two OpenAI requests.
Production is not accepted for general testing. The other three canaries were not started.
Target application commit: `391a41fe3cae2ce22bc4ac4f69ea840b472f8447`.
Recorded provider cost: 37.387 cents ($0.37387), estimated from actual token usage.
No generated version, render proof, published deck or export was produced.

## Scope and release order

Project `af0ad057-2bac-4a20-84d4-92999008271c`, production
`62b96a38-4f13-49d6-8a9e-64f664f8abc8`.
Frontend: https://instantdeck.aistack.codes
API: https://deck-api-production-94be.up.railway.app
Renderer: https://deck-renderer-production.up.railway.app

Canonical stages: browser presigned upload, scanned ingestion, extraction/OCR,
source publication from contiguous current-source page records, generation,
compilation (one validation repair if necessary), isolated browser render proof,
publication, visible slides, secure renderer Print/Save as PDF.
Source miniatures are disabled for Instant uploads and cannot gate completion.

The request maximum is shared across settings, ORM defaults, creation, worker
eligibility and generation. Request two requires a recorded first-attempt
compilation failure. Request three is rejected. Existing operation dollar caps
are preserved; new operations default to NULL (uncapped), with usage accounting.
Zero is invalid. Token limits, quota, leases, deadlines and isolation remain.

Migration 20260908_0001_instant_cost permits NULL, removes the old column default
and relaxes the cost CHECK. It updates no existing operation rows. Migration
20260908_0002_request_default changes only the server default for future rows to 2.
Both are compatible with existing rows and old writers that explicitly supply
500 cents. Old workers are not compatible with new NULL operation caps: deploy
the render-proof worker (with pre-deploy migrations) first, then the generation
worker and renderer, and finally the API and frontend. This upgrades every
consumer before new operations can use NULL caps. Preserve existing row
limits. Do not downgrade the nullable migration after NULL operations exist;
rollback requires a compatible application release. The migration explicitly
refuses a lossy downgrade.

## First historical failure, read directly from production

Deck `deck_f47c338758056655`; operation `instantop_32cdfa2d0175daa3`;
attempt `instantattempt_ee3e4dd42a637f0a`;
provider request `req_342a8f9a0be84c5f9c998d066821eed6`.
Provider HTTP 200; 32,683 input / 18,370 output tokens; recorded cost 22.4554 cents.
Saved validation summary: failed, blocking `presentation_visual_storytelling_missing`.
The compiler requires visual content on min(3, ceil(section count / 3)) sections.
The first response failed that coverage gate. The subsequent repair could not
start because the worker had persisted a maximum of one request. This was not
an OpenAI balance failure. No historical operation was retried or changed.
Existing regression: test_v15_rejects_a_text_only_document_template.

Prior online canary `deck_e7736227e84ba3a3` separately failed
`grounding_target_invalid`; operation `instantop_644236b33df4ebd9`, attempt
`instantattempt_c4d45bc72d3f20f2`, provider request
`req_8b33330713c64b34afe08aa01853d59d`. HTTP 200, 32,701 input / 15,710 output tokens,
19.7976 cents. Its single-request persisted maximum also prevented repair.
Neither source publication nor these HTTP 200 responses produced a published deck.

## Gate audit before deployment

| Gate | Reviewed code default / intended behavior | Railway before release | Persisted / enforcing boundary |
|---|---|---|---|
| Provider starts | Exactly 2 from shared policy | Unset; old runtime default 3 | DB default 3; historical rows 1; worker/operation lock |
| Validation retry | One, only after recorded compilation failure | Code-owned | Attempt validation summary; no replacement operations |
| Per-operation dollar cap | Unset means NULL; zero rejected | Unset on all relevant services | Old DB default 500; old rows 500 preserved; precharge/checkpoint/settlement |
| Cost accounting | Actual input/output tokens and estimated tariff cost retained | Enabled | Provider-attempt and operation counters |
| Model | Exact gpt-5-2025-08-07 | Matches API and generation worker | Provider attestation and locked binding |
| Token limits | Input <=272,000; output default32,000 <=128,000; context <=400,000 | Defaults | Feasibility and operation row |
| Whole HTML bytes | 512,000 default | Unset/default | Request envelope and compilation |
| Source pages | At most25, exact current-file/run contiguous records | Old thumbnail-dependent publication | DeckSlide lineage; new publication check |
| Source miniatures | No new Instant job; historical optional jobs ignored/skipped | Generation worker still lists miniatures | Source dependencies/read model/dispatcher corrected |
| Context/vector jobs | Not required for Instant | Source enrichment/context excluded from Instant chain | Source-stage selector |
| Operation deadline | 1,200s, max1,800s | Default1,200s | Generation monotonic deadline |
| Provider timeout | 1,200s, max1,800s | Default1,200s | Provider transport; no unbounded retry |
| Job retries | Ingestion1, bounded per-stage attempts; paid attempts independent | Code defaults | WorkflowJob attempts and terminal-operation guard |
| Queue/lease | PostgreSQL queue, locked claims, 15-minute refreshed leases | One generation and one dedicated preview worker | Durable job state/heartbeats |
| Worker concurrency | Sequential worker dispatch | One replica per relevant worker | Process loop; four canaries strictly sequential |
| Quota/idempotency | Existing product quota and command key enforced | Daily generation quota1,000,000 default | Reservation/charge and unique request identity |
| Instant feature | Must be enabled | Enabled | API precharge and renderer readiness |
| Frontend API URL | Exact production API above | Correct | Frontend server proxy |
| Frontend/API origins | instantdeck.aistack.codes | API/worker instead configure instant.deck.aistack.codes | CORS/origin settings require correction |
| Renderer parent | Exact live frontend origin | deck-v2-production.up.railway.app | Frame ancestor/capability isolation; requires correction |
| Authentication/CSRF | Ordinary account, same-origin cookies, authenticated capability | Prior browser signup/signin succeeded | Frontend CSRF + API bearer ownership checks retained |
| Storage | Shared bucket/endpoint; presigned browser PUT and scanned completion | Configured; previous upload completed | Stored file size/checksum and source extraction |
| Encryption | Existing renderer and workspace encryption keys | Relevant key presence verified; renderer keys match | Encryption-purpose boundaries; no rotation |
| Database | Core URL matches all four backend services; AI URL matches API/worker | Matches, values redacted | Private SQL via supplied SSH key |
| Malware scan | Real clamscan; fail closed; refresh signatures at source image build | Signature database dated2026-09-01 | Completion scan and worker readiness |
| Browser dependencies | Playwright1.54 + Chromium in image | Installed Chromium1181 | Isolated render-proof worker; required, not a thumbnail |
| Validation/publication | No raw output publication; validate/render proof first | Earlier jobs blocked after generation failed | Immutable DesignVersion plus publisher transaction |
| UI reconciliation | Failed job remains failed on direct navigation; stop terminal polling | Empty version misleadingly asks for first generation | Reconciliation fix and failed-job mode serialization |
| Export | Secure full-deck capability, isolated popup, print published output | Canonical workspace lacks button; Export route404 | Added action and legacy-link redirect |
| Release identity | Bake commit into image and log at startup | Only historical CLI labels and image digests | New DECK_BUILD_COMMIT build argument; runtime BUILD_REVISION |

Runtime signatures and final upload/CORS behavior must be rechecked after release.
An SSH shell UID is not evidence of the application's process UID.

## Tests and local evidence

Full backend suite: 118 passed; 425 deprecation warnings (primarily utcnow),
including actual Chromium geometry/contrast/type tests. Initial runs lacked
Playwright or were blocked by sandbox socket restrictions; rerun in the prepared
runtime with Chromium outside that sandbox passed. No provider calls in unit tests.
Frontend check/build and reconciliation tests are recorded in release evidence;
16 pre-existing Svelte warnings in4 files are retained, not concealed.
Local source-only test: all52 records/markers across7/10/15/20 pages persisted,
including OCR pages8 and8/17, with zero thumbnails. This is not a browser upload
or generated-deck acceptance. Both migrations applied to local PostgreSQL.

## Rollback targets captured before deployment

| Service | Deployment | CLI label revision (not independently runtime-verified) |
|---|---|---|
| Frontend | 3c44829e-212c-4d57-b5a5-09ec54c6e265 | 8fb27fd92db55c26fca5311a25b399707ae1bcda |
| API | 3245902e-cce3-49a5-bfff-a5a2ea28a6d8 | 8fb27fd92db55c26fca5311a25b399707ae1bcda |
| Generation/source worker | 424e87d5-e708-49fd-bbc1-7d12605901ed | 8fb27fd92db55c26fca5311a25b399707ae1bcda |
| Render-proof worker | af5caf55-9cbc-470b-81ff-752e24a78bf5 | 8fb27fd92db55c26fca5311a25b399707ae1bcda |
| Renderer | b24e9aab-f839-45a7-a0df-d84e618a671b | 5b8848f578ca6540f9df8ee3ea0028d87a0deb50 |

Full image digests and service manifests are in private release evidence.
No separate scheduler or source-processing service exists in this project;
source processing shares the generation worker. API pre-deploy owns migrations.

## Acceptance ledger

| Canary | New operation | Generated live / refreshed / exported |
|---|---|---|
| 7 pages | `instantop_c262eed1d36c8b0e` (2/2 starts) | Failed compilation twice; no render or export |
| 10 pages | Not started: stopped after 7-page failure | Not verified |
| 15 pages | Not started: stopped after 7-page failure | Not verified |
| 20 pages | Not started: stopped after 7-page failure | Not verified |

Production is not declared ready until all four rows pass every live criterion.

## Completed rollout evidence

The clean deployment archive contains 1,314 files, each byte-verified against
commit `391a41fe3cae2ce22bc4ac4f69ea840b472f8447`. Private artifacts, ignored
inputs, PDFs and environment files are excluded. A documentation-only successor
`4298752c08b0a235bb6fbcaf109c01909b4172e7` initially reached the two workers;
all five final service identities were aligned to the explicitly pinned commit
before the canary started. The application code in these two commits is identical.

Production SQL confirms core migration head `20260908_0002_request_default`.
The cost column is nullable with no default; the provider-start default is 2.
The two historical operation rows retain their 500-cent and one-start limits.
Renderer service configuration now explicitly selects `/railway.renderer.toml`.
All five staged service configurations were read back with the pinned build
commit and no `INSTANT_HTML_MAX_OPERATION_COST_CENTS` variable.

The user confirmed an $85 monthly OpenAI project ceiling. Enforcement has not
been verified or changed: project administration access and the OpenAI project
ID are still unavailable. Railway hosting usage is separate; its existing
workspace spend limit was unset and has not been changed. Do not describe the
OpenAI ceiling as enforced based on this release configuration.

## Final deployed identities

All five `/app/BUILD_REVISION` values equal `391a41fe3cae2ce22bc4ac4f69ea840b472f8447`.
The API runtime source hashes also match the clean Git archive.

| Service | Deployment | Image digest |
|---|---|---|
| preview | `ea4104ce-a5f1-4ed9-9498-1cf2227f6e63` | `sha256:d546e88e5155b246e4d828e1ae1d4393fa2057038b30df5e51121db414af1e2c` |
| worker | `2e385269-7c5e-4efe-b35b-956d94d0ceef` | `sha256:2036702dc3fd65ffeee5a82ee4b1c8d56d626bdc052cba5a32d2712ec42754e2` |
| renderer | `542e7d2d-339a-4a6f-9049-18360473068a` | `sha256:1809ea88bbc0710fb4895c6a50e4949425544b478b284b595a8d3bd7863ea041` |
| api | `93ae166f-be88-4c82-b197-3858c2746d1f` | `sha256:edac1d6b1bda1734f1838edef7ebd6f1b0f92f010057a0ef88ee5e48b21c587d` |
| frontend | `dc1f5a83-00a8-49ef-b5c4-e92e3f2811b2` | `sha256:011e6b544dda24faaca28b1b3b528a5189ebbb4e4508777fa29e0755b0d66434` |

Dedicated ordinary browser account: `canonical-canary-b45ba6ea36@example.com`.
Production signup and signin both completed through the frontend.
The transient Railway control-plane HTTP 503 affected status reads only; no
replacement frontend deployment was created.

## Exact live reproduction

1. Sign up and sign in at `https://instantdeck.aistack.codes/auth/sign-up` and
   `/auth/sign-in` using the dedicated ordinary account recorded above. Owner
   `usr_63c04257168e974b`, role `user`, workspace `ws_4007dd95e89a987b`.
2. Open `/decks/new?firstBatch=slide_miniatures`, leave the default Instant Deck
   mode selected, and use the real Chromium file selector to upload
   `ignore/instant-deck-canary-07-pages.pdf` (11,692 bytes, seven pages).
3. Let the frontend complete its upload and navigate automatically to
   `/decks/deck_8bb26b00a171b8a0/processing?instant=1`. Do not click Regenerate,
   Retry Instant Deck, or submit another upload.
4. Observe processing through two provider responses and terminal failure,
   approximately 486 seconds after file selection. Inspect the same deck via
   `/decks/deck_8bb26b00a171b8a0/instant-deck`, refresh, and revisit processing.
5. Stop: no export action or generated iframe exists, so Print/Save as PDF
   cannot proceed. No raw response was published or exported diagnostically.

This deployed upload page uses its existing same-origin multipart proxy, not a
browser presigned PUT. The earlier presigned-upload requirement was therefore
not exercised; no presigned/CORS acceptance is claimed or simulated.

## Browser and API evidence

| Browser request | Result | Timing / correlation |
|---|---|---|
| POST `/api/products/deck-aistack-codes/decks/upload-session` | 200 JSON | 204 ms; Railway `6lZflUiwR4eqrBOnjq4OvQ` |
| POST `/api/products/deck-aistack-codes/decks/upload` | 200 JSON; source persisted and ingestion accepted | 8,680 ms; `upload-bc707045-8cee-457c-965e-e7bcf8d0e4cb`; Railway `RJfhr-XDRxGSoOchWUN5dQ` |
| GET `/api/products/deck-aistack-codes/decks/deck_8bb26b00a171b8a0/workflow-state` | 138 responses, all 200 JSON | Median 389.55 ms; maximum 1,219.35 ms; final Railway `DA54d9bpRd-UiqzC9I3ezw` |

No failed browser requests, console errors, CORS errors, or authentication
redirect loops were observed during this upload. The apparent waiting period
was provider generation, not an HTTP request hung between frontend and API.
The final JSON reported `phase=failed_final`, `status=failed_final`,
`canOpenInstantDeck=false`, `canOpenSmartDeck=true`, `nextAction=manual_review`.

Production API HTTP logs independently show the same deck workflow request:
`2026-09-08T15:58:58.433338090Z GET /api/products/deck-aistack-codes/decks/deck_8bb26b00a171b8a0/workflow-state 200`,
133 ms, request `S4o_7beDTCuBU717lt7tkg`, host
`deck-api-production-94be.up.railway.app`.

## Persisted canary identity and state transitions

Deck `deck_8bb26b00a171b8a0`; frontend workflow
`deckwf_deck_8bb26b00a171b8a0`; extraction run `process_7478e78d856f1403`;
source file `file_63e7500a7b7046e5`.
Operation `instantop_c262eed1d36c8b0e`; generation job
`job_01a86efd7191b9a1`. Exactly one operation exists for this deck.

| Stage | Job ID | Final state |
|---|---|---|
| source_ingestion | `job_1a3762d928ca7f53` | `completed` |
| source_extraction | `job_5259a06692fff627` | `completed` |
| db_publisher | `job_d2906bfdef637a57` | `completed` |
| brand_extraction | `job_bb2d4dd246c9b0e8` | `completed` |
| instant_deck_generation | `job_01a86efd7191b9a1` | `failed_final`; presentation_investor_narrative_incomplete |
| schema_validation | `job_780fc02b63b2d0a1` | `blocked`; dependency_failed |
| preview_render | `job_6cfe2f5f22b98cf2` | `blocked`; dependency_failed |
| db_publisher | `job_949a54adac72f572` | `blocked`; dependency_failed |

Ingestion completed at 15:51:37 UTC; extraction at 15:51:42; source publication
at 15:51:42.819750. All seven current-file/current-run page records were
contiguous and every expected page marker matched. There were zero thumbnail
jobs. The seven-page input has no OCR-only pages. OCR-only pages in the 15- and
20-page inputs remain untested online because the sequence stopped.

The operation moved through `provider_running` on the initial request, recorded
its failed validation, then `provider_running` on its repair, and finally
`failed_final` at 15:59:19 UTC. Its request maximum was 2 and its cost cap NULL.
Generation never produced a DesignVersion. Downstream jobs became
`blocked/dependency_failed`; compilation, render-proof, DesignVersion and
generated-slide tables contain no rows for this deck. The source deck's
`status=ready` describes retained source readiness, not generated acceptance.

## OpenAI attempts and bounded cost

Model: `gpt-5-2025-08-07`. Costs below are persisted tariff estimates based on
actual input/output tokens; they are not an invoice assertion.

| Attempt | Provider request | HTTP | Input / output tokens | Cost |
|---|---|---|---|---|
| `instantattempt_d1089338480304a9` (generation) | `req_7d420bfc102442e58b3abe2b6a27b771` | 200 | 27,948 / 16,430 | $0.199235 |
| `instantattempt_10ec22b845117b2a` (deterministic_validation_retry) | `req_238994b52b8e407c801f5e394b09e27e` | 200 | 27,948 / 13,970 | $0.174635 |

Initial request: 15:51:51.922450 → 15:56:07.520402 UTC (255.598 seconds),
client request `da8ad7d1-854f-43e7-9258-b3e272b95920`.
Repair: 15:56:07.571275 → 15:59:19.703986 UTC (192.133 seconds),
client request `e99012ec-f788-45ce-b57a-c08aa032b168`.
Total: 55,896 input / 30,400 output tokens; **$0.373870**.
Both attempts have known outcomes and encrypted, quarantined checkpoints.
A final SQL read after browser navigation still showed exactly two starts,
one operation, and no publication. No third start or replacement was attempted.

## First failing boundary and root cause

The first failing boundary is **provider output → HTML compilation**, specifically
`presentation_investor_narrative_incomplete`. This is not a balance, upload,
queue-consumer, provider availability, renderer or storage failure.

An audited application read decrypted only the synthetic canary checkpoints in
remote memory and returned structural counts, enum labels and hashes. No raw
HTML, source copy, credentials or session values were exported into this report.

- Attempt one produced six sections. It included all four required composition
  families but failed the compiler's minimum of seven sections. The deployed
  v17 prompt listed composition families but did not state that numeric minimum.
- Attempt two produced seven sections and omitted `people-proof` and
  `capital-plan`. It failed the same gate. Its count also mirrored the seven-page
  source, which would fail the subsequent independent non-mirroring gate.
- The so-called repair sent **identical system and user prompts**. The loop
  recorded the compiler error and continued without adding any feedback.
  The permitted second request was therefore a blind regeneration.

Both persisted attempts have identical hashes:

| Binding | Hash |
|---|---|
| System prompt | `33805d0b8b149384b2a252bf67c772dfb57cac3c693cbebcac7422f7815ab753` |
| User prompt | `0a3dc0efdee379a1dcc93d77df1410650336b8e1e2ae61b987ed7a00ab59d0db` |
| Request envelope | `4a511f0583e8c8e2189c06f626a7ad7f150fede57e965f0a668f5aabe0b5a1f1` |
| Provider/source binding | `f7bf93cd6350e0011b1a664ca98cf40dfc2986d1a37956abe19a6c153dc6283f` |

Redacted worker evidence: source job IDs above occur at
`2026-09-08T15:51:45.140873478Z` through `15:51:45.140895128Z`.
At `2026-09-08T15:59:22.868283159Z`, the worker logs
`ERROR deck_worker_job_failed`. That error line lacks a deck correlation ID;
its attribution relies on the matching persisted job failure and timestamp.
No canary-specific renderer or render-proof execution logs exist because their
work was blocked before dispatch. Absence of these logs is not render acceptance.

## Final browser and export result

Processing, direct navigation, and refresh all visibly display
“We couldn't finish the Instant Deck” and “no generated version was published.”
Each has zero generated HTML frames, zero Print/Save as PDF buttons, and zero
workflow-state polls during a subsequent 15-second observation. Terminal
workflow polling stops correctly.

A separate footer incorrectly displays **Slides ready** in all three views.
Its dashboard read model checks `canOpenSmartDeck` (source readiness) before
failure or canonical Instant publication. The processing page also recommends
a fresh regeneration. These are additional product UI defects, not evidence
that generated output was published. No regeneration action was clicked.

**Visible generated slides: no. Refresh/direct-navigation acceptance: failure
shown correctly, readiness banner incorrect. Render proof: not reached.
Publication: not reached. Product PDF export: not reached.**

## Local follow-up fix — not deployed

The repository follow-up keeps all validation, grounding, isolation, token,
quota, deadline, cost-accounting and two-start guards in place:

- Adds system prompt v18 with the compiler's explicit investor section minimum
  and seven-page/non-mirroring guidance. The exact deployed v17 prompt hash
  remains supported for historical request verification.
- Adds `instant_html_validation_repair.py`: versioned compiler-code feedback
  bound to the recorded first failure, preserving the original source bytes and
  system prompt. It contains no raw provider response or copied source text.
- Updates `full_html_generation_service.py` and
  `instant_html_operation_service.py` to persist the repair's distinct request
  envelope and lineage. Token feasibility and cost reservation include the added
  feedback. Recovery reconstructs and checks it, including when only the second
  attempt is supplied; modified feedback, diagnostics or prompt hashes fail closed.
- Updates `workspace_dashboard_read_model.py` so terminal failures override
  source readiness and Instant readiness requires canonical publication.
- Updates `frontend/src/routes/(product)/decks/[deckId]/processing/+page.svelte`
  to offer status navigation rather than suggest another paid request.
- Adds `test_instant_validation_repair_feedback.py` and
  `test_dashboard_instant_readiness.py`, covering the real two-attempt transport
  loop with a fake provider, accounting, third-request rejection, immutable
  recovery, prompt compatibility, and source-versus-generated readiness.

Final local checks: **127 backend tests passed**, including actual Chromium;
579 existing-style deprecation warnings are retained. Frontend check: zero
errors, 16 existing warnings in four files. Frontend production build passed;
all four reconciliation tests passed. `git diff --check` passed. The two existing
prompt-version contract tests were updated for v18; the new regression verifies
that historical v17 still has the exact deployed hash.
No additional live provider requests were used to test the fix. Passing local
regressions does not establish that OpenAI will produce accepted output online.

## Remaining blocker and next action

Production remains on the explicitly authorized `391a41f` release. The follow-up
source changes require their own review and deployment authorization. The failed
7-page operation is exhausted and must not be replaced under the original run.

**Single next action:** review and authorize the follow-up release together with
one new, explicitly bounded 7-page acceptance operation. Only after that passes
should the 10-, 15- and 20-page sequence resume. Do not open general user testing.
The separate $85/month OpenAI ceiling still needs verified project-admin access;
this task has not configured or verified it.

Private, ignored evidence is under `backend/.artifacts/canonical-release/`:
deployed identities, pre/post configuration, read-only SQL snapshots, redacted
network traces and logs, structural checkpoint diagnostics, and browser failure
screenshots. These files and all PDFs are excluded from the release archive.
