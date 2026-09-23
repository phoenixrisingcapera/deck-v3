# Local Instant Deck release review — 2026-09-09

Earlier accepted operations passed all four synthetic local canaries. However,
the final seven-page run on `841ec5e` failed render proof on 2026-09-09 (details
below). The current revision therefore **does not meet final local acceptance**.
The latest release instructions require a reviewed commit and exact-SHA approval
before deployment. Railway is not accepted for general users; no online
success is inferred from local results.

## Accepted operations

| Source pages | Deck | Operation | Generated slides / PDF pages | Provider requests | Recorded dollars |
|---|---|---|---|---|---|
| 7 | `deck_facea51c497fd8bf` | `instantop_69af4bc2e74bfe14` | 7 / 7 | 1 | 0.187499 |
| 10 | `deck_3063cb0ef2831a09` | `instantop_23026b326eee954d` | 7 / 7 | 1 | 0.220400 |
| 15 | `deck_c83c8cb8f917842e` | `instantop_4b6846890d60c866` | 8 / 8 | 1 | 0.252294 |
| 20 | `deck_e8f59eb3a461cfea` | `instantop_bf3a84b9de6123e6` | 8 / 8 | 2 | 0.428165 |

Each operation used an ordinary dedicated account, browser file selection and the
actual frontend upload route, real malware scan/extraction, OpenAI generation,
compiler, isolated Chromium proof, publisher transaction and generated workspace.
Every source page/marker persisted; OCR page 8 (15-page source) and pages 8/17
(20-page source) were verified. No source thumbnail jobs were required or created.

All 30 generated browser slides and all 30 exported PDF pages were visually
inspected. No blank content, clipping, overlap, broken images or irrelevant
investor material was found in the accepted outputs. Refresh, direct navigation,
processing-page navigation and slide controls passed. Terminal published views
stopped workflow polling. Print opened the isolated published document and
Chromium produced the PDF; the native operating-system print dialog was not
automated. These small PDFs take the product's multipart upload route. They do
not establish acceptance of its separate large-file presigned PUT branch.

Frontend: `https://localhost:5443`; API: `http://127.0.0.1:8010`;
renderer: `https://127.0.0.1:8012`; local PostgreSQL port 55432; MinIO TLS port
59000. Source/generation and render-proof workers ran separately. Core and AI
migration heads applied. Browser UI used the supported Vite TLS local runtime.

## Observed fixes

The first browser operation incorrectly received the investor objective. General
uploads now carry an explicit general intent; investor rules apply only to an
explicit investor/pitch type in the persisted generation command. No source
phrase or free-form goal can infer investor mode; absent type remains general. Manual regenerate
also preserves the source's intent. General decks retain grounding, narrative,
meaningful visuals, layout, safety and nonempty-content checks, with no investor
section families, investor count or source-page count equality constraint.

Successive observed failures drove individual repairs to source-column retention,
SVG grounding/geometry/labels, measured text ownership and painted backgrounds,
transparent-wrapper overflow, content width and image/text sizing. Exact bounded
compiler diagnostics identify invalid fact IDs, tags and section locations.
Immutable historic prompt/compiler decoders remain available.

Repair v3 supplies the verified, encrypted first HTML alongside the exact saved
compiler issues. The 20-page accepted run first failed negative SVG bar heights;
its second request repaired those errors, compiled, rendered and published eight
slides. Distinct request-envelope hashes and deterministic production binding
recovery were verified against persisted records. Request three remains rejected.
A truncated provider body may retrieve that same stored response once by ID,
within the original deadline; it never replays the generation POST. This fallback
has mocked transport coverage, not a confirmed successful live fallback event.

Print now uses the same 1920 × 1080 CSS canvas as render proof and works through
nested document wrappers. Downstream failures remain failures after navigation;
“Check status” reconciles the existing operation rather than suggesting another
paid attempt. Dashboard/source-ready corrections from the preceding follow-up
are retained. A final Chromium regression also exposed low-contrast labels in
the separate deterministic metric template; labels now sit above their bars on
the slide's ordinary foreground/background pair.

## Verification and limits

- Complete backend suite: **162 passed**, including real Chromium; 579 existing
  deprecation warnings. Stale current-version assertions were updated while
  historic prompt assertions and security/grounding gates remain.
- Frontend reconciliation tests: **5 passed**. Svelte check: **0 errors**, the same
  16 existing warnings in four files. Production frontend build passed.
- Both production Dockerfiles built locally from source-only contexts. Backend
  image includes refreshed ClamAV signatures, OCR and Playwright Chromium 1181.
- All 30 accepted published slide documents also passed the production image's
  Chromium **139.0.7258.5**: non-root, network disabled, geometry/contrast,
  individual and whole-deck quality gates. No persisted proofs were altered.
- The built frontend correctly rejects localhost API URLs at startup. Its
  production configuration guard was not changed; local UI acceptance uses Vite.
- After final service restarts, all four already-published decks again passed
  browser direct/processing navigation, refresh, slide controls and PDF export;
  zero terminal workflow polls in each 15-second check. Private evidence:
  `backend/.artifacts/local-final-browser-review/`.
- No further paid operation was made during final review or regression testing.

Across the entire observed repair investigation: **37 operations, 54 generation
starts, $10.014239 known recorded cost and four transport-unknown billing
outcomes**. No active operation; every operation retained its two-request limit.
Unknown billing is not treated as zero. Accounting uses recorded token tariffs,
not the provider invoice. The requested $85 account/project monthly ceiling has
not been configured or verified; project billing administration remains separate.
No per-deck dollar cap was introduced. Token limits, deadlines, leases, quotas,
idempotency, scanning, renderer isolation and publication gates remain active.

Detailed iteration IDs, failures and changes are in
[local-product-journey.md](local-product-journey.md). Private evidence is under
`backend/.artifacts/local-product-iteration-*/`; accepted runs are 25/7, 25/10,
27/15 and 34/20. Corrected 7-page export is in iteration 25-export-fixed. PDFs,
provider bodies, credentials, session state and screenshots are excluded from Git.
Diagnostic launchers remain local and are excluded from the release; unrelated
pre-existing work and the user's `.gitignore` edits are preserved unstaged.

## Deployment after exact-SHA authorization

Project `af0ad057-2bac-4a20-84d4-92999008271c`, production environment
`62b96a38-4f13-49d6-8a9e-64f664f8abc8`.
Frontend `https://instantdeck.aistack.codes`;
API `https://deck-api-production-94be.up.railway.app`;
renderer `https://deck-renderer-production.up.railway.app`.

All five application services require a coherent release: API, source/generation
worker, render-proof worker, renderer and frontend. Deploy a clean archive of the
authorized full SHA, passing that SHA as `DECK_BUILD_COMMIT`; do not deploy the
working directory or an unpinned branch. Verify runtime `BUILD_REVISION` on each.

1. Recheck there is no active generation crossing the version transition. Keep
   ordinary intake closed during coordinated rollout; do not change customer rows.
2. Upgrade render-proof worker and renderer to support the new compiler, then
   source/generation worker, API and frontend. Verify each deployment SUCCESS and
   runtime identity before proceeding. No new migration is introduced here;
   retain the existing nullable-cap and two-request-default migrations.
3. Verify origins, renderer parent, storage/scan readiness and existing account
   spending controls without exposing credentials. Leave the operation cost cap
   unset; retain accounting and exactly two generation starts.
4. Run one fresh live 7-page browser canary. Require publication, visible slides,
   navigation/refresh and export before the 10-, 15- or 20-page live tests. Keep
   general-user acceptance closed until the live journey passes.

## Rollback targets

Read-only Railway deployment lookup on 2026-09-09 confirmed all five targets
remain SUCCESS. Their previously verified runtime revision is
`391a41fe3cae2ce22bc4ac4f69ea840b472f8447`; this review did not re-read runtime files.
Full image digests remain recorded in
[canonical-production-release.md](canonical-production-release.md#final-deployed-identities).

| Service | Deployment |
|---|---|
| Frontend | `dc1f5a83-00a8-49ef-b5c4-e92e3f2811b2` |
| API | `93ae166f-be88-4c82-b197-3858c2746d1f` |
| Source/generation worker | `2e385269-7c5e-4efe-b35b-956d94d0ceef` |
| Render-proof worker | `ea4104ce-a5f1-4ed9-9498-1cf2227f6e63` |
| Renderer | `542e7d2d-339a-4a6f-9049-18360473068a` |

Before new artifacts exist, restore these application images coherently if the
rollout fails. After v29 artifacts or v3 repair attempts exist, old consumers
cannot decode them: use a compatible rollback release retaining the new decoders,
with intake paused, instead of downgrading blindly. Preserve all operation rows,
limits and evidence. Never downgrade the nullable-cap migration lossily.

The next authorized external action is approval of the exact new commit SHA.
No deployment, branch push, live paid operation or opening to general users is
included in this local release-review step.

## Explicit-intent correction and existing 20-page continuation

After the stricter user clarification, removed source-phrase inference of investor
mode. The existing intent regression now proves even source text saying “Investor
pitch deck” remains general unless an explicit investor type is supplied. Seven
existing focused intent/repair/recovery/request-limit tests passed; no tests added.
The previous complete 162-test suite and Docker-image checks remain recorded above;
they preceded this narrow classification correction.

At the user's direction, continued only the existing 20-page operation
`instantop_bf3a84b9de6123e6`, deck `deck_e8f59eb3a461cfea`. Reauthenticated the
dedicated browser session and verified all eight published slides, direct and
processing navigation, refresh, slide controls and eight-page PDF export again.
Zero console errors and zero terminal polls in 15 seconds. No replacement
20-page operation or new provider request was made for this continuation.

Before that steering arrived, one newly initiated seven-page operation
`instantop_f824e0f381082036` (deck `deck_80f7ef6036bd892c`) had already started
one provider request. It was terminalized through the existing operation service
with `user_stopped_canary`. Its in-flight response returned HTTP 200, 30,294 input /
13,281 output tokens, **$0.170678** recorded; compilation recorded
`svg_rect_geometry_invalid` in section 5. No second request started, no version
was published, and the original maximum of two remained unchanged. No further
canary or speculative repair followed.

Updated accounting: 38 local operations, 55 generation starts, **$10.184917**
known recorded costs plus the same four unknown billing outcomes; no active
operation. Deployment remains paused; the new classification correction requires
its own exact-SHA authorization. Rollback targets above remain unchanged.

## Final seven-page run — render contrast failure, investigation blocked

The existing 20-page operation was preserved. All eight browser slides and all
eight exported PDF pages were visually reinspected from
`backend/.artifacts/local-final-browser-review/canary-20/`; no clipping, blank
content, overlap, broken images or investor material was observed. No new
20-page operation or provider request was created.

The subsequently authorized final seven-page browser upload used unchanged
application revision `841ec5e6b2b6624704e1f07f6fbcdd0cba4832d9`, system prompt v38,
compiler v29, the existing dedicated account and the real ignored seven-page PDF.
Local frontend/API/renderer URLs remain those recorded above.

- Deck: `deck_f0fc12dc5e675056`.
- Workflow: `deckwf_deck_f0fc12dc5e675056`.
- Generation: `job_9c6d784a62896a2d`.
- Schema validation: `job_07e1a41e8d6a7f2c`.
- Render proof: `job_43de35a5c68abdc5`.
- Publisher: `job_1208f7718be4e12f`.
- Operation/attempt IDs and recorded cost: **pending database verification**.

Browser `POST /api/products/deck-aistack-codes/decks/upload-session` and multipart
`POST /api/products/deck-aistack-codes/decks/upload` returned 200. Upload request
ID: `upload-3ab6d54e-038c-4585-8063-365783856fb6`. The captured workflow response
records ingestion/extraction/source publication completed, generation completed
at 09:13:09 UTC and schema validation completed at 09:13:09 UTC. The serial worker
log between this deck's brand completion and generation completion contains
**two provider starts and two successful responses**. Exact attempt diagnostics,
request hashes, tokens and settlement still require the persisted record read.

The first observed failing boundary is **render proof**, error
`preview_render_failed`, starting at 09:13:10 UTC. Its metrics list failed contrast
keys `body-01` through `body-12`; clipping, overflow, console errors and failed
images are absent. The underlying cause is not yet determined: inspect the saved
HTML and measured foreground/background pairs before deciding whether generated
styling or contrast measurement is wrong. No speculative code change was made.

At about 254 seconds the browser visibly showed “We couldn't finish the Instant
Deck” and stated that no deck was published. API `canOpenInstantDeck` was false;
the failed proof blocks publication. Generated slides were not displayed and
export was not achieved. The failure message exposes internal render metrics and
overflows its panel; this is a separately observed UI issue, not repaired ahead
of the first failing boundary. The bottom “Slides ready” notification names the
previously published 20-page deck, not this failed seven-page deck.

Private evidence: `backend/.artifacts/local-product-iteration-36/canary-07/`,
including `processing-result.png`, `network-upload.json`, `terminal-ui.txt` and
`final-run-observed-failure.json`. No replacement operation was started.

Automatic approval review rejected the read-only local database inspection because
the Codex usage limit was reached. The already-authorized browser process was
allowed to finish; its saved files and ordinary local logs supplied the evidence
above. Restoring Codex execution allowance is required to inspect this same
operation and resume the small observed-fix loop. No workaround was attempted.
Final regression/build checks, complete diff review and a new commit remain
pending; no deployment authorization is requested for this failing revision.

Preserve the historical **$6.912569 plus two transport failures with billing
unknown** checkpoint in the iteration history. The later pre-final-run audit was
**$10.184917 plus four billing-unknown outcomes**, 38 operations and 55 starts.
This final run adds a deck and two logged starts, but its cost is unverified,
**not zero**; do not mislabel missing inspection as a provider transport failure.

Edits since the last progress report are the announced root log/instructions,
these factual report updates and ignored evidence. Application code is unchanged.
The user's `.gitignore` and pre-existing untracked diagnostic files are preserved;
diagnostics are excluded from the release. No push, deployment or new SHA was made.

## Release preparation after restored access and latest Railway instructions

The user authorized committing/merging to main and a Railway deployment, then
supplied a more specific release instruction requiring the new full SHA and a
stop for exact-SHA authorization. This preparation follows that latest gate.
The candidate contains the accumulated implementation through `841ec5e`; the
new commit adds the root bitácora/instructions and this updated failure evidence.
No unreviewed application change is included, and the known failure is not fixed
or described as accepted.

Restored database access confirmed final local operation
`instantop_f8b451acf9499a05`, version `designver_a366ea2e7c61562787154489`:

| Attempt | Provider result | Compilation | Tokens in / out |
|---|---|---|---|
| `instantattempt_63498bc4f65280ec` | HTTP 200 | `grounded_fact_unknown`, paragraph in section 5 | 30,313 / 13,894 |
| `instantattempt_a3d65cba1fb859c9` | HTTP 200 | Passed | 40,226 / 11,245 |

Request-envelope hashes differ: first
`f88eee947a531caade86468ad6c94f105571996e42ed04ecfc8b3fc9c410c91a`, repair
`899546ad249ab67d43191c8a6920350a9fc131ea3d92118d94671bd093306f3a`.
The operation retained max two starts and a NULL dollar cap, recorded
**$0.339564**, and finished `failed_final` / `render_proof_failed`. Publisher is
`blocked` / `dependency_failed`, with zero persisted passing proofs.

Inspection of the existing output identified the cause: the provider put light
SVG text fills in nested SVG `style` elements. `_sanitize_tree` clears unsupported
SVG tags before collecting their CSS, so those style bodies are lost and label
fills fall back to black on dark diagrams. The slide 3 screenshot confirms the
unreadable labels; measured contrast is approximately 1.17:1 against the 3:1
threshold. Diagnostic rendering finds the same issue on slides 5 and 6. This is
a compiler styling-loss defect, not a false contrast alarm. No security check
was relaxed and failed output was not published.

Known local investigation accounting is now **$10.524481**, with the same four
transport billing-unknown outcomes. The historical **$6.912569 plus two unknown
outcomes** checkpoint is preserved; the final run's cost is now settled rather
than unknown. No new provider request was made during this release preparation.

Final existing checks on the application revision: **162 backend tests passed**
(real Chromium, 579 existing warnings), **5 frontend tests passed**, Svelte check
**0 errors / 16 existing warnings**, and frontend production build passed. These
checks do not replace the failed browser acceptance. Production Docker builds
from the earlier review remain historical; no new Docker build is claimed here.

Railway preflight rechecked all five rollback deployment IDs above as SUCCESS.
Read-only production SQL reported 22 terminal failed and 5 completed operations,
with no active operation at inspection. Two-start settings, unset per-operation
caps, worker roles and corrected origins match the earlier release configuration.
The account/project $85 ceiling remains unverified. Public signup was already
enabled; no technical intake pause has been applied yet and no general-user
acceptance is asserted. Intake must be paused for an authorized rollout.

The requested Railway MCP is reachable through its authenticated CLI stdio proxy.
MCP environment-status and service-config reads are recorded privately under
`backend/.artifacts/release-20260909/`; configuration reads omit secret values.
No deployment, restart, variable mutation or live canary has been performed.
The exact source diff is generated from the committed snapshot, with ignored
PDFs, credentials, private evidence and diagnostic launchers excluded. The user's
unrelated `.gitignore` changes stay unstaged.

The prerequisite that this exact application revision completed final local
browser-to-export acceptance cannot be confirmed. Approval must not be inferred
from the older accepted seven-page operation or the passing regression suite.
