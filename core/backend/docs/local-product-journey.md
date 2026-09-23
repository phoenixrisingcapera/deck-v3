# Local Instant Deck product journey — 2026-09-08

Status: all four local canaries accepted on 2026-09-09. Final release review in progress. No follow-up deployment authorized or performed.
Local browser acceptance is required before any release request.

## Stack and boundaries

- Frontend: https://localhost:5443 (SvelteKit, local TLS)
- API: http://127.0.0.1:8010
- Renderer: https://127.0.0.1:8012 (separate hostname and origin, production credential isolation; corrected during iteration 10)
- PostgreSQL: local port 55432, separate core/AI databases; both migration heads applied.
- Storage: local MinIO HTTPS port 59000.
- Real sequential source/generation and separate render-proof worker processes.
- Real ClamAV 1.5.3, verified official main/daily/bytecode signatures; fail-closed upload scan.
- OCR tools and real Chromium installed; no scan or render-proof bypass.
- Two provider starts maximum per operation, null per-operation dollar cap, token/deadline and accounting guards retained.
- Existing secured OpenAI generation key read only by the local API/provider worker. Renderer and render-proof worker receive no provider credential.

The PDFs, local environment, browser sessions, inert provider responses, screenshots
and PDFs remain in ignored paths. Raw output is inspected privately and is never
published as a substitute for validated product output.

## Iteration 1 — actual browser upload, current v18 follow-up

Deck `deck_2b2ea0d17d7e6264`; operation `instantop_a50492eef3c245c8`;
generation workflow job `job_5624414fb42248ed`.

Browser signup/signin and upload passed; malware scan recorded clean.
All seven source pages and markers persisted. Zero thumbnail jobs.

| Attempt | Result | Compiler error | Tokens input/output |
|---|---|---|---|
| `instantattempt_a36e2afac7fa3967` | HTTP 200, eight sections, two SVG sections | `presentation_visual_storytelling_missing` | 28,041 / 15,033 |
| `instantattempt_9e0aba711550d51c` | HTTP 200, eight sections | `presentation_investor_narrative_incomplete` | 28,190 / 14,083 |

Two requests, total recorded tariff estimate **36.1449 cents ($0.361449)**.
Final state `failed_final`; no DesignVersion, render proof, publication or export.

Request envelope hashes differ:

- Initial: `dcdbda844f86e13b4e9a70ecf3b454fa397fb8df1130252fb2243871f64ecb91`
- Repair: `0b8f8380a821b1f357b899c543bf6e181214221ea87abfa9441a953ef5e5313f`

Observed root cause: ordinary upload supplied an investor-ready VC objective.
The request treated a processing presentation as an investor deck. The repair
then failed for omitting the irrelevant `people-proof` composition family.
The initial visual-coverage failure remains a legitimate quality requirement.

Small correction prepared: preserve the previous prompt for replay; use a neutral
upload objective and explicit general/investor intent; select investor validation
only for an identified investor pitch. Preserve general quality checks and allow
section count to be chosen independently of physical page count. Local frontend
Instant uploads no longer submit an Investment Committee/diligence default.

Focused regression: `test_general_upload_intent.py`: **1 passed**. A seven-section
general presentation from seven source pages is accepted by the general quality
contract; a source explicitly identified as an investor pitch still needs its
investor narrative. This test is not product acceptance.

Browser failure verification: processing, direct navigation and refresh all show terminal failure, with no misleading Slides ready banner, no print action, no generated iframe and zero workflow polls during each 15-second terminal observation.

Only the API and source/generation worker were restarted; the frontend picked up
its change through its development server. The existing failed operation was not
retried or reset. A fresh sequential local operation follows the user's explicit
iterative-canary authorization.

## Acceptance ledger

| Canary | Current result |
|---|---|
| 7 pages, iteration 25 | PASS after targeted print correction: published, all seven slides visually inspected, navigation/refresh and seven-page PDF export verified. |
| 10 pages, iteration 25 | PASS: first request, seven generated slides/proofs, visible navigation/refresh and seven-page PDF export. |
| 15 pages, iteration 27; OCR page 8 | PASS: eight generated slides/proofs, visible browser navigation/refresh and eight-page PDF export. |
| 20 pages, OCR pages 8 and 17 | PASS, iteration 34: two requests, eight generated slides/proofs, OCR pages 8/17, visible navigation/refresh and eight-page PDF export. |

All four local acceptances are verified below. Online acceptance remains pending.

Iteration 2 persisted request verification: `audience=General audience`, `deckType=general`, `presentationIntent=general`, neutral redesign objective. All seven pages/markers are present, no thumbnail jobs.

## Iteration 2 — general generation passed; render metric failure

Deck `deck_caf53092d532844d`; operation `instantop_4405d1037b974e76`.
One HTTP 200 request, 27,734 input / 13,142 output tokens; **$0.166088**.
Compilation passed with seven sections and no people-proof/capital-plan family.
DesignVersion `designver_0e91f54bd8eb064affdae62d` was compiled but never published.
The real preview worker failed on slide 4: table-container contrast ratio 1 and
vertical overflow. Six other slides passed individual Chromium checks.

Actual screenshot and DOM inspection established two metric false positives at
this boundary: the table container painted no text of its own (all keyed cells
were legible), and root scrollHeight 1081 vs clientHeight 1080 came from fractional
padding. The content bottom was 1009.28125; the document remained 1080px high.

Small correction in `playwright_render_child.py`: check text ownership instead of
container textContent; allow one CSSOM rounding pixel while retaining independent
clipping checks. One real Chromium regression passed, including rejection of a
low-contrast cell and genuine larger overflow. Reinspection of the exact seven
sanitized documents passes every individual and aggregate quality check. This
is private diagnostic evidence, not publication or browser product acceptance.

Only the local render-proof worker was restarted. Iteration 3 will perform a
fresh sequential browser upload, as explicitly authorized. Cumulative generation
cost so far: **$0.527537**, three provider requests across two operations.

## Iteration 3 — repair worked; SVG render boundary failed

Deck `deck_3a463f32ef5e836e`; operation `instantop_23911c11fe6418a9`.
Two HTTP 200 requests, 55,684 input / 24,765 output tokens; **$0.317255**.
Initial compilation failed `presentation_translucent_background_forbidden` for
a table background with alpha 0.08. The existing feedback-guided second request
corrected it and passed compilation with seven general sections. Envelope hashes
`d0e0a2935fc848c0b0d2acb83ecf35324828b2825400b5078d8cc2ab4aa02067`
and `de77990bf92ea56bdba5180d9c90c5ff27f70cb66c9f5bba1b94069a5adf1447` differ.

Real render proof failed on SVG `decoration-01` contrast. Screenshot inspection
found overlapping sentence-length SVG labels on slide 3. The old metric checked
the SVG container colour, not actual text fill, and did not detect those overlaps.
The targeted measurement correction gives SVG text deterministic diagnostic keys
and checks glyphs against their actual solid painted background. Its one focused
Chromium regression passes and still rejects unreadable and overlapping labels.
Reinspection now accurately rejects the overlap and orange-on-light SVG labels
rather than claiming the deck is ready. No validation rule was bypassed.

Prompt v20 retains historical v19 bytes and adds specific SVG label width,
wrapping and contrast guidance. The next sequential operation tests this observed
correction. No previous operation is reset or republished. Cumulative recorded
generation cost after three operations: **$0.844792** (five requests).

## Iteration 4 — individual slides passed; full-deck gate failed

Deck `deck_4a75cd1704004563`; operation `instantop_7b856cfedd28cce4`.
Two HTTP 200 requests, 55,472 input / 26,999 output tokens; **$0.339330**.
Initial request took roughly eleven minutes and was rejected for table-row
striping (`tbody tr:nth-child(odd) td`). A focused regression confirms this
selector survives section isolation while root-section positional selectors
remain rejected. The narrow validator correction is prepared for the next run.

The distinct feedback repair passed compilation and all seven individual slide
proofs. Aggregate validation correctly rejected three near-white slides (maximum
two) and only one qualifying substantial visual (minimum three). Actual visual
ink ratios for the diagram slides were .0809, .0083, .0199 and .0122. Screenshots
show small marks inside large empty panels. Nothing was published or exported.

Prompt v21 retains historical bytes and adds the exact aggregate thresholds and
post-scaling visual-area budget, with wider meaningful diagram guidance. A single
regression preserves rejection of these observed aggregate metrics. No quality
threshold was relaxed. Cumulative cost after four operations: **$1.184122**,
seven provider requests. Next action is the fifth sequential local browser run.

## Iteration 5 — remaining SVG scaling failure

Deck `deck_4bb785b64ee33354`; operation `instantop_77bcf44ac9650b2d`.
Two HTTP 200 requests, 56,619 input / 27,484 output tokens; **$0.345614**.
The initial response failed `grounding_target_invalid` on SVG text in section 3.
Its repair passed compilation and every individual render check. Aggregate proof
still rejected visual coverage: only one diagram qualified. Two other diagrams
rendered into narrow columns, producing ink ratios .0198 and .0295 despite large
source viewBox coordinates. The near-white limit now passes. No publication.

The browser account session expired during the long investigation. Real browser
sign-in restored the same account and resumed the same operation without another
upload. The existing workflow continued independently of the browser session.

Small changes: prompt v22 explicitly gives required primary diagrams a full-width
row instead of a narrow text-adjacent column. Exact repair contract v2 transmits
the complete recorded compiler issues (including tagName and sectionOrdinal),
preserves v1 replay, hashes the distinct envelope, and rejects investor diagnostics
for general intent. Its focused deterministic-recovery regression passes.
Cumulative cost after five operations: **$1.529736**, nine requests.

## Iteration 6 — full-width visuals exposed automatic grid placement

Deck `deck_ab9e41bf49862b6d`; operation `instantop_86ff373a70f03200`.
One HTTP 200 request, 28,190 input / 12,851 output tokens; **$0.163748**.
Seven sections compiled. Render proof rejected real clipping: unplaced body
paragraphs occupied one narrow grid cell beneath the now full-width diagrams.
A transparent SVG rectangle also caused a false contrast failure.

Compiler v23 adds a zero-specificity full-row fallback for direct body paragraphs;
explicit source placement still wins. The renderer skips fully transparent SVG
paint when calculating background contrast and visual ink. Actual Chromium also
identified 20px of empty trailing padding as scroll overflow with all content
inside the canvas; overflow now checks descendant boxes and text ranges, while
retaining independent clipping rejection. Three focused Chromium tests pass.
The exact saved output privately recompiled under v23 passes all seven individual
proofs and aggregate visual requirements. This does not alter or publish the
failed operation. Cumulative six-operation cost: **$1.693484**, ten requests.

Iteration 7 starts a fresh sequential browser upload with these observed fixes.

## Iteration 7 — generation and compilation passed on request one

Deck `deck_52606852df0819d9`; operation `instantop_b4380e8cda90fce6`;
job `job_0c219619bfa0f6e7`; attempt `instantattempt_12d041469df37fb2`.
HTTP 200, 28,467 input / 13,599 output tokens; **$0.171574**.
Seven general sections passed compilation v23. Source scan, all seven records and
markers passed without thumbnail jobs. Render proof and publication are being
observed; no acceptance claimed yet.

Iteration 7 terminal result: real browser shows failure; preview job failed
`preview_render_failed`, operation `render_proof_failed`, publisher blocked.
The first clipped slide had an unplaced marker div collapsed into one grid column.
Compiler v24 extends the zero-specificity fallback to direct items in the two
observed content-grid containers; explicit source spans retain precedence.
Focused Chromium regression passes. The response separately contains negative
SVG bar heights, retained as a distinct observed issue rather than silently
normalizing or publishing them. Cumulative seven-operation cost: **$1.865058**,
eleven provider requests. No deck has yet published.

## Iteration 8 — SVG translucent paint measurement

Deck `deck_5cede8b7c5c2e704`; operation `instantop_7da93eaa708ebe63`;
attempt `instantattempt_e78335017f91cfa7`. One HTTP 200, 28,224 input /
14,367 output tokens; **$0.178950**. Seven sections compiled under v24.
No upload/network error or clipping in the first failing slide. The real render
worker rejected twelve SVG labels with unknown contrast: the checker did not
composite translucent SVG panels over their background. A focused Chromium test
preserves readable translucent panels and rejects dark text on those panels.
The saved diagram also appears too small with crowded labels; correcting its
contrast measurement alone is not visual acceptance. The operation remains
failed, publisher blocked, browser terminal failure truthful.
Cumulative eight-operation cost: **$2.044008**, twelve requests.

## Iteration 9 — label extends outside its contrast-safe node

Deck `deck_62e9d891c9fc9251`; operation `instantop_ea3be1b149eb8a00`;
attempt `instantattempt_382802f54dbedc0f`. One HTTP 200, 28,241 input /
13,694 output tokens; **$0.172241**. Seven sections compiled under v24.
The first failed render is accurate: a 22px sentence extends outside a 300px dark
process node onto a bright teal surface, producing contrast 1.5633 against a
required 4.5. No clipping or missing source records. A chart separately repeats
invalid negative rectangle heights. Publication remains blocked and UI failed.

Prompt v23 targets the first observed failure: short stage labels inside small
nodes, full grounded explanations in HTML below, explicit backplate inset.
Focused Chromium regression retains rejection of the sentence spillover and
accepts the short label. Historical prompt v22 remains replayable.
Cumulative nine-operation cost: **$2.216249**, thirteen requests.

## Iteration 10 — first actual publication and export; visual review still fails

Deck `deck_ccc7af9a4ee8c07d`; operation `instantop_4acf83c75366d6f4`;
job `job_8400db00bf5cd47d`; DesignVersion `designver_ed27b731392070e87cced1cf`.
Request one `instantattempt_777fc79becf8f0a9` failed `grounding_target_invalid`
on SVG text in section 5. Request two `instantattempt_eba9fb6382f35123` corrected
it. Two HTTP 200 responses, 57,243 input / 28,255 output tokens; **$0.354104**.
Real repair-v2 reconstruction verified exact structured compiler diagnostics,
general intent, deterministic recovery and distinct envelopes:
`14289373d1bfef5e36506af25a4735bd207a5af1fc93ebb8708a86a042f0ad28`
and `1886cb123155e91393ddcaca74d644e72be25c38430e3ab9274bb85e7303ec50`.

Seven render proofs and publication completed; operation checkpoint `published`.
Initial browser display exposed a local-only configuration error: different
localhost ports still share cookies, and the cookieless renderer correctly
returned 400. Local renderer hostname changed to **https://127.0.0.1:8012**;
frontend stays https://localhost:5443. No credential guard was weakened. The same
published operation then loaded via processing navigation, direct URL and refresh.
Slide navigation passed; product Print/Save as PDF produced seven pages, 63,347
bytes, 960x540pt, and terminal workflow polling stopped (zero requests in 15s).

Every exported slide screenshot was inspected. Slide 6 has a rotated final-node
label whose edge extends slightly beyond its contrast-safe box. Browser automation
passed, but **visual acceptance remains failed**, so larger canaries are not started.
The contrast metric now samples glyph-box edges as well as centres; its exact
Chromium regression catches the spill and accepts a fitted label. Prompt v24
allocates all process nodes before drawing, avoiding a squeezed rotated final node.
Cumulative ten-operation cost: **$2.570353**, fifteen requests.

Additional visual comparison of iteration 10 with the original source page 5:
the generated chart reverses the first four category magnitudes instead of
preserving the source's ascending 38/62/78/91/100 percent series. Merely retaining
all numeric strings did not preserve their category associations. This is another
reason that browser/export automation success is not full canary acceptance.
The next run's chart must be checked against the source as well as for clipping.

## Iteration 11 — final-node correction passes; chart slide clips

Deck `deck_f56e4455775477e8`; operation `instantop_0148a5ac25f1bb53`;
job `job_7a3735fb67d50392`. Request one `instantattempt_e4e9edcf3f9b5812`
failed `grounding_target_invalid` on SVG text in section 5; its distinct v2 repair
`instantattempt_7aea85aab1775e50` compiled seven sections. Two HTTP 200 requests,
57,508 input / 26,636 output tokens; **$0.338245**. Six individual slides pass,
including the corrected process labels; slide 5 has real vertical clipping.
The operation is failed and publisher blocked. Cumulative cost **$2.908598**,
seventeen requests. Larger canaries remain unstarted.

A source comparison traced iteration 10's wrong chart associations to
`build_slide_blocks`: `pdftotext -layout` retained the columns, but the builder
replaced raw page text with whitespace-collapsed paragraphs. The one-line source
correction preserves original page layout text while keeping normalized blocks.
One real-PDF regression fails before and passes after this correction: numeric
values retain their spatial association to their category labels. Only the
source/generation worker needs restarting for the next fresh browser upload.

## Iteration 12 — source chart associations corrected; duplicated evidence overflows

Deck `deck_01696e787261029b`; operation `instantop_02543472cbb8c0f7`;
attempt `instantattempt_1aa56b46269c96fc`. One HTTP 200, 28,726 input /
13,749 output tokens; **$0.173398**. Compilation passed seven sections.
The exact encrypted request was checked in memory: all five original chart
category/value associations survive. The rendered chart now correctly shows
38/62/78/91/100 in the original ascending category order.

Render proof rejected overflow on slides 3 and 5: a large visual is followed by
vertical lists of repeated source evidence. Chart labels additionally use light
text over bright bars. The operation remains failed, publisher blocked.
A focused compiler regression proves numeric facts may be grounded on the SVG
root without duplicate HTML lists, while grounding on SVG text remains rejected.
Prompt v25 targets this duplicate inventory: ground the visual itself, keep
remaining explanations in a compact grounded caption, and budget their height.
Cumulative twelve-operation cost: **$3.081996**, eighteen requests.

## Iteration 13 — compiler rejection followed by transport-unknown repair

Deck `deck_906574b7eea88b27`; operation `instantop_7cc704f8fb7a0c26`.
Attempt `instantattempt_37bc6d1b16f78e09` returned HTTP 200, 29,084 input /
15,314 output tokens; **$0.189495 recorded**. Compilation rejected
`presentation_translucent_background_forbidden` in actual table/card/frame CSS.
The existing v2 repair allocated attempt `instantattempt_ff0e684c93016578` and
then received a TLS EOF. State `transport_unknown`, no provider request ID or
HTTP response, billing outcome unknown. The operation correctly stopped at two
starts, failed, with no artifact or publication. It was not reset or resubmitted.
DNS and an unauthenticated HEAD subsequently reached OpenAI (401); no generation
or credential was sent for that connectivity diagnosis.

Prompt v26 clarifies the observed forbidden translucent HTML panel declarations;
one focused regression preserves rejection and accepts an opaque surface.
Cumulative known recorded cost **$3.271491**, twenty provider starts, plus the
unknown billing outcome of iteration 13 attempt two. No fully accepted 7-page run.

## Iteration 14 — SVG grounding repair compiles; invalid bar geometry blocks proof

Deck `deck_f3628ef6f812cbde`; operation `instantop_73e904d35d56e150`;
job `job_7f41b1d9254b93fe`. Two HTTP 200 requests, 57,649 input /
28,414 output tokens; **$0.356202**. First `grounding_target_invalid`
on SVG text in section 5; exact-feedback repair compiled seven sections.
Six slides pass isolated inspection; slide 5 emits five Chromium errors because
provider-authored rectangle heights are negative, so the bars are absent.
Operation failed, publisher blocked, accurate terminal browser failure.

Compiler v25 makes grounded SVG text/tspan labels read-only manifest entries,
retaining fact allowlisting and section lineage. Historical v24 stays strict.
The focused regression passes; the saved first response now privately compiles
without publication or a provider call. Prompt v27 describes this exact contract.
Known cumulative recorded cost **$3.627693**, 22 provider starts, with iteration
13 repair billing still unknown. Iteration 15 is the next fresh browser run.

## Iteration 15 — grounding passes first try; SVG arithmetic is invalid

Deck `deck_18b5aaae0b4d1d41`; operation `instantop_ff3f8b5b290aa725`;
job `job_114e5150e5bf120c`; attempt `instantattempt_e6ecb8a9ae68afae`.
One HTTP 200, 29,186 input / 14,411 output tokens; **$0.180593**.
Seven sections compile with read-only grounded SVG labels. Render proof rejects
overlapping sentence labels on slide 3 and five invalid SVG coordinate attributes
on slide 5. The provider put unevaluated arithmetic in rectangle y attributes,
producing an incorrect chart. Publication remains blocked. The browser session
expired while waiting; it was renewed using ordinary sign-in for the same deck.

Compiler v26 detects invalid rectangle lengths and negative dimensions before
rendering, with actionable structured `svg_rect_geometry_invalid` feedback.
It neither evaluates provider expressions nor guesses corrected geometry. One
focused regression passes; saved actual output produces the exact new error.
This makes the existing bounded compiler repair eligible for that real defect.
Known cumulative recorded cost **$3.808286**, 23 starts, plus the still-unknown
billing outcome of iteration 13 repair. Larger canaries remain unstarted.

Post-sign-in browser inspection of iteration 15 exposes a separate terminal UI
defect: direct/refresh offers first-generation guidance even though render proof
failed. Processing correctly shows failure. The global Slides ready notice was
traced to the OTHER earlier published deck `deck_ccc7af9a4ee8c07d`, not source
readiness of this failed deck; the broad browser text match was misleading.
There is no generated iframe or print action and terminal polling stops. The
compiled-but-unpublished direct-navigation failure is not covered by the earlier
generation-failure correction and remains a targeted follow-up blocker.

## Iteration 16 — geometry repair succeeds; SVG contrast measurement is wrong

Deck `deck_fbf763c27ec728a6`; operation `instantop_06b2651555b58099`;
job `job_20159392bfbb99da`. Two HTTP 200 responses, 57,815 input /
28,718 output tokens; **$0.359449**. First attempt
`instantattempt_ee335c31f4086a97` failed `svg_rect_geometry_invalid`;
repair `instantattempt_8be6c146e1178322` compiled seven sections with correct
positive bar geometry and original ascending chart values. Exact structured
feedback, distinct envelope hashes and deterministic reconstruction were verified
in memory against the real request checkpoint; intent is general.

Six slides pass isolated render inspection. Chart labels visibly contrast against
a dark field, but the checker reports 1.062:1 because it treats an unpainted CSS
background on SVG text as real. Chromium exposes that computed background from
the HTML body guard while painting no such box. The operation remained failed,
with publication blocked and the processing page showing failure (~841 seconds).

Small correction: ignore CSS backgrounds on non-root SVG graphics when resolving
painted surfaces; use SVG fill for tspan as well as text. One focused Chromium
regression verifies readable grounded labels and continued rejection of a truly
unreadable tspan. All five SVG metric regressions pass. Known cumulative recorded
cost **$4.167735**, 25 starts, plus unknown billing of iteration 13 repair.

## Iteration 17 — transport failure before provider response

Deck `deck_bd8aa94164ba51a3`; operation `instantop_b4afa920810294d2`;
job `job_c0df8e66639ce1ac`; attempt `instantattempt_ee5f89e43fa2a6f0`;
client request `8e77032b-7b90-4faf-9417-1cb0be2cb66a`. The browser upload,
scan and seven page markers passed. One provider start failed during TLS send
with `ssl.SSLEOFError` / `urllib.error.URLError` in about 0.53 seconds.
State `transport_unknown`, no HTTP status, provider request ID, token usage or
output. Billing is unknown, not assumed zero. The operation is terminal and was
not reset or retried. An unauthenticated OpenAI HEAD returned 401 afterward.
Known cumulative recorded cost remains **$4.167735**, 26 starts, plus two unknown
billing outcomes (iteration 13 repair and iteration 17 first request).

Separately, the observed iteration 15 direct-navigation defect is corrected by
consulting the matching authoritative workflow outcome after workspace loading.
A terminal failure's primary action checks status instead of starting a fresh paid
request. One focused reconciliation regression passes, including preservation of
a previous published version and exclusion of failures from an older operation.
Browser verification uses the same failed deck without a provider request.

The same iteration 15 deck now passes real-browser terminal checks on processing,
direct navigation and refresh: failure is visible, no first-generation suggestion,
no current-deck Slides ready link, no generated frame, no print action and zero
workflow polls in each 15-second terminal observation. Screenshot inspection
confirms the primary action is Check status. The global ready notice still links
to the other historical published local canary. No provider request was needed
for this UI verification.

## Iteration 18 — active fresh browser run

Deck `deck_cf8d3f8d781fa7d2`; operation `instantop_7da41359b10db391`;
job `job_15c18adb7d3cb8e1`. Actual browser upload and scanned source extraction
passed; all seven current-source page markers exist, zero thumbnail jobs. The
first provider request returned HTTP 200: 28,906 input / 15,004 output tokens,
**$0.186173 recorded**, attempt `instantattempt_69bcfa067adbc3df`. Compilation
rejected negative rectangle height with `svg_rect_geometry_invalid`. The second
request is the bounded feedback-guided repair and remains in flight. No
publication or success is inferred from downstream queued jobs. For this small PDF the actual frontend chooses its
normal multipart product upload route; presigned browser PUT is selected by the
application only for larger files. No claim of a direct storage PUT is made for
this local small-file journey.

Iteration 18 terminal result: both HTTP 200 requests, **$0.363868**, total 58,014
input / 29,135 output tokens. Repair `instantattempt_3270629566046e3c` compiled
seven sections; version `designver_4d1a59be28d2d186c2b42b29` published with seven
render proofs and every workflow stage complete. Processing navigated into the
workspace after about 1,105 seconds. Real browser direct/refresh/processing
navigation, slide selection, visible sections and secure print popup succeeded.
Chromium exported seven 960x540-point PDF pages (55,604 bytes), with zero terminal
workflow polling during the 15-second check.

Every slide screenshot was visually inspected. Content is legible, nonempty and
general; chart category/value associations are correct. However, slide 6's final
rectangle starts at x=1240 with width=210 in a 1440-wide SVG viewBox: its right
corner is cropped by 10 SVG units. **This is not a fully accepted canary.** The
10-page run remains blocked by this visual defect.

Compiler v27 batches invalid SVG lengths and out-of-viewBox rectangles in grounded,
untransformed evidence diagrams. It does not infer transformed geometry or ban
decorative cropping. One focused regression reproduces the actual 1240+210>1440
defect, proves earlier v26 behavior is retained for recovery, and verifies that
invalid bar and cropped-node diagnostics reach one feedback response together.
Prompt v28 states the same geometry rules up front. The existing focused geometry
and SVG grounding tests pass (four tests).
Known cumulative recorded cost **$4.531603**, 28 provider starts, plus two unknown
billing outcomes. All larger canaries remain unstarted.

## Iteration 19 — valid geometry; investor palette quota leaks into general proof

Deck `deck_e6f2cb724bee8423`; operation `instantop_91cd9636606fbf5a`;
job `job_37645f3fddf0c78d`; attempt `instantattempt_7d92a4b07db73273`.
One HTTP 200, 28,917 input / 13,746 output tokens; **$0.173606**.
Compilation passes on request one with the new upfront SVG geometry rules.
All seven isolated slide checks pass, including contrast, geometry and diagram
fit. Aggregate proof rejects only `presentation_near_white_deck_exceeded`: three
white-dominant slides exceed the inherited maximum of two. No publication.

All seven screenshots were inspected. The general presentation's white surfaces
are readable and source-appropriate; imposing the investor palette quota is an
incorrect contract boundary. Compiler v28 binds trusted presentation intent into
the compilation hash and manifest; proof creation and proof retrieval use it to
apply the white-field quota only to investor/legacy contracts. General decks keep
background measurement, contrast, legibility, source grounding, visual coverage,
structure, safe content, render isolation and publication gates. Prompt v29
expresses this intent-specific rule. A focused regression uses the exact observed
metrics, retains investor/legacy rejection, verifies insufficient general visuals
still fail, and proves different intents produce different compilation hashes.
The general/investor narrative regression also passes.

Manual inspection additionally flags awkward, column-interleaved caption wording
on slide 3. That remains a content-coherence check for the next real output;
palette measurements alone cannot establish acceptance. Known cumulative recorded
cost **$4.705209**, 29 starts, plus two unknown billing outcomes. Larger canaries
remain unstarted.

## Iteration 20 — intrinsic wrapper width shrinks primary visuals

Deck `deck_14622ac9177b77cd`; operation `instantop_dec76f54ad56569f`;
job `job_0405b60871ecca48`; attempt `instantattempt_dd5fedbd9b691f7f`.
One HTTP 200, 29,307 input / 15,422 output tokens, **$0.190854**.
Seven source markers, no thumbnails, compilation passed. All individual slide
checks pass but aggregate proof rejects `presentation_visual_storytelling_missing`.
The browser shows terminal failure after about 232 seconds; publication is blocked.

Actual slide screenshots reveal the chart and process diagram shrink to roughly
500px: their centered grid wrapper has `max-width` and auto margins but no width.
Prompt v30 explicitly requires wrapper width as well as maximum width and budgets
the resulting full-size visual height. One focused Chromium regression reproduces
the shrinkage and confirms an explicit width restores the 1440x420 chart within
the slide. Historical v29 request bytes are preserved. No quality gate is relaxed.
Known cumulative recorded cost **$4.896063**, 30 starts plus two unknown billing
outcomes. Iteration 21 will exercise this correction through a fresh browser upload;
all larger canaries remain unstarted.

## Iteration 21 — full-width diagrams; unwrapped SVG sentences overflow nodes

Deck `deck_b5c7a36d1fbe7748`; operation `instantop_528a51b4e50e027b`;
job `job_c1715d42770bb839`; attempt `instantattempt_2f3696c8ab2fd591`.
One HTTP 200, 29,446 input / 13,689 output tokens, **$0.173698**.
Scanned source records and compilation pass. Six individual slide proofs pass.
Slide 3 fails contrast keys `decoration-01-text-2/4/6/8`, measured ratio 1.5633
against threshold 3. The width correction works, but four full SVG sentences
spill beyond their 260px nodes, overlap adjacent sentences and cross the teal
background. No publication or export; the browser shows terminal failure.

Prompt/validation v31 adds a deterministic single-line SVG format constraint:
longer than 32 characters requires explicit positioned tspan lines or short node
labels with full explanations in grounded HTML. It does not claim to measure font
fit; isolated Chromium contrast/overlap/clipping gates remain mandatory. This
catches the actual four failures during compilation so the existing second request
can receive structured `svg_label_wrapping_required` feedback. One focused test
checks all four diagnostics, exact feedback, a distinct request hash and deterministic
repair reconstruction. Private replay of the actual response confirms v30 still
passes and v31 rejects those four labels. Known cumulative recorded cost
**$5.069761**, 31 starts plus two unknown billing outcomes. Larger PDFs unstarted.

## Iteration 22 — transparent grid-wrapper padding falsely reported as clipping

Deck `deck_c219ea23c9694882`; operation `instantop_db5213fa1064f6f0`;
job `job_e03a30f7bbf50747`; attempt `instantattempt_c63b87468b83b742`.
One HTTP 200, 29,304 input / 13,621 output tokens, **$0.172840**.
Compilation passes. Proof rejects slides 3/4 solely for `overflowY:true`, with
no clipped element keys, contrast errors, image errors or severe overlaps.
Browser terminal failure observed around 201 seconds; publication blocked.

Actual DOM measurement identifies only transparent `.section-inner` wrappers
outside the canvas: bottoms 1133.96875 and 1192.75. Their text, diagrams and
painted child panels remain within the 1080px canvas. Renderer overflow measurement
now distinguishes unpainted wrapper padding from painted boxes and independent
text ranges. Focused Chromium tests retain rejection of clipped text, colored
panels and borders (two tests including the existing padding regression pass).
All seven saved slides and the general aggregate proof pass a private diagnostic
recheck; every screenshot was inspected, chart values match the source, no
investor content or blank slides. The failed operation was not republished, and
this diagnostic is not product acceptance. The next fresh browser run must still
publish, display, refresh and export. Known cumulative recorded cost **$5.242601**,
32 provider starts plus two unknown billing outcomes. Larger canaries unstarted.

## Iteration 23 — published and visible; source-caption and PDF acceptance fail

Deck `deck_1a117347647d490b`; operation `instantop_60992dfefa972d2d`;
job `job_0c63057577893f00`; attempt `instantattempt_5a8150fe4108e393`;
version `designver_48b4f0d056abde88fb615555`. One HTTP 200, 29,526 input /
12,494 output tokens, **$0.161848**. All seven source records, compilation,
seven proof rows and publication pass. Browser processing navigation opens the
workspace around 171 seconds. Direct navigation, refresh and slide selection
work; terminal workflow polling stops (zero during 15 seconds).

All seven browser screenshots inspected. No blank slides or investor sections;
chart associations correct. But slide 3 copies a column-interleaved caption.
The raw source page retains layout; source blocks and their factual catalog
previously collapsed it. The targeted extraction/context correction preserves
raw paragraph line breaks and columns through the fact catalog while retaining
normalizedText, title normalization and source identities. One focused regression
and the earlier native-chart test pass (two tests). No historical source rows changed.

The real Print / Save as PDF popup also exposes an independent downstream defect:
seven browser sections measure 1904x1176; export yields **10 pages instead of 7**,
81,139 bytes, 960x540pt. The private automated browser report originally said
passed because it checked only a nonempty PDF; manual-acceptance.json records
false and the exact discrepancy. Future harness runs explicitly compare PDF
page count with generated section count. No acceptance.json is written. Fix
the source boundary first, then revisit the observed pagination failure.
Known cumulative recorded cost **$5.404449**, 33 starts plus two unknown billing
outcomes. The 10/15/20-page inputs remain unstarted.

## Iteration 24 — source layout fixed; repaired chart has one invisible label

Deck `deck_62a02ee8c05ee483`; operation `instantop_b30ef050f9fd3466`;
job `job_c57880e4b88fc2bd`. The exact immutable provider request preserves
column spacing/newlines in source blocks AND source facts. First response
`instantattempt_cf003169964583db` returns coherent pipeline descriptions but
five negative SVG bar heights: `svg_rect_geometry_invalid`, section 5.
Request two `instantattempt_c7d54b7c936651c1` contains all five exact recorded
issues; its distinct envelope hash and deterministic reconstruction were verified.
Both HTTP 200; total 59,608 input / 29,441 output tokens, **$0.368921**.

Repair compiles seven slides; six isolated slide checks pass. Slide 5 fails
`body-06` contrast at ratio 1 against threshold 3: its dark `100%` text is above
the orange bar, on the dark canvas, and visibly disappears. Other chart labels
and source values are correct. All seven screenshots inspected; pipeline
caption coherence is repaired in both responses. No publication or export.
Browser reports terminal failure around 861 seconds.

Prompt v32 explicitly distinguishes above-bar labels from labels inside the
highlighted bar. One focused Chromium regression preserves rejection of dark
text above the orange bar, and verifies light text above / dark text inside
pass. Existing contrast gates remain unchanged. The separate nested-wrapper
print-selector defect observed in iteration 23 remains to be fixed after this
rendering boundary. Known cumulative recorded cost **$5.773370**, 35 starts
plus two unknown billing outcomes. Larger canaries remain unstarted.

## Iteration 25 — published, but print changes the validated canvas

Deck `deck_facea51c497fd8bf`; operation `instantop_69af4bc2e74bfe14`;
job `job_a0867834318e9b92`; attempt `instantattempt_1e4a3be7f3c01029`;
version `designver_4174273eeda0f5476408956d`. One HTTP 200, 29,535 input /
15,058 output tokens, **$0.187499**. Seven extracted pages, seven compiled
slides, seven isolated proofs and publication pass. The browser opens the
workspace around 202 seconds; direct navigation, refresh and selection work.

Every browser slide and all seven PDF pages were visually inspected. The browser
slides have coherent captions and correct chart values, with no investor material.
But PDF page 3 clips its heading and final bullet: the export contract changes
the validated 1920x1080 canvas to 1280x720. Seven PDF pages alone are not success.
The manual acceptance remains false, despite automated page-count checks passing.

Targeted fix: print at the same 1920x1080 CSS-pixel canvas (20x11.25in pages),
and select compiler-marked slide roots irrespective of the source wrapper.
This also addresses the observed nested-wrapper pagination failure from run 23.
One real Chromium regression verifies each nested/root slide produces exactly
one PDF page and retains text at both canvas edges. No validation/publication
or capability checks changed. Only the local API and renderer restarted.
The same published deck is being re-exported without another provider request.
Known cumulative recorded cost **$5.960869**, 36 starts, including two attempts
with unknown additional billing. All operations retain the two-start maximum.

Iteration 25 corrected export: **PASS**. Seven PDF pages, 51,481 bytes,
1440x810pt; every page visually inspected and complete. Browser slide selection,
direct navigation, refresh, processing navigation and zero terminal polls pass.
Same immutable published artifact; no extra provider request. Evidence retained
in a separate export-fixed directory so the original clipped PDF remains available.
This is the first accepted local seven-page deck. Continue sequentially to 10 pages.

## 10-page canary — first run passes without a code change

Deck `deck_3063cb0ef2831a09`; operation `instantop_23026b326eee954d`;
job `job_300e9c7de048b5a9`; attempt `instantattempt_3d146e4762093195`;
version `designver_87cce38ef06bf1773d6d2941`. One HTTP 200, 38,352 input /
17,246 output tokens, **$0.220400**. All ten source records and markers
persisted, zero thumbnail jobs. Compilation and seven isolated proofs passed;
publication completed and the processing page opened the workspace at 252 seconds.

The general presentation consolidates repeated source material into seven
generated slides; source-page count is not imposed on generated-section count.
Every browser slide and PDF page visually inspected: meaningful complete content,
correct chart values, no clipping/overlap/blank slide/broken image/investor material.
Direct navigation, refresh, selection and processing navigation pass; zero
terminal polls during 15 seconds. Product Print / Save as PDF produces seven
pages, 60,850 bytes. No new code change or repair request was necessary.
Known cumulative cost **$6.181269**; two earlier attempts still have unknown billing.
Next is the 15-page canary, including actual OCR extraction on page 8.

## 15-page canary, first run — OCR recovered; image/caption layout clips

Deck `deck_cb218cb8d3761206`; operation `instantop_b21a35ea5b0fcbb1`;
job `job_16d07d17797d408e`; attempt `instantattempt_24ed6b2b7a8875d8`;
version `designver_0afbdb76a817f4dad8666b80`. One HTTP 200, 49,492 input /
17,014 output tokens, **$0.232005**. All 15 source pages/markers present, page 8
recorded as `pdf_ocr`, zero thumbnail jobs. Eight sections compile successfully.

Real isolated render rejects slide 7: `overflowY=true`, clipped `headline-01`,
`body-03`, `body-04`. Screenshot/geometry show a 1440x813.5 image plus text
centered into 1080px: heading begins at -40.90625px and final captions end at
1120.921875px. Seven other isolated slides pass. Publication stays blocked;
processing shows terminal failure at 243 seconds. This is actual clipping, not
a metric false positive. No repair was started because compilation passed and
the existing second-request policy only permits compilation repair.

Small correction: prompt v33 instructs bounded image frames when images share
a slide with grounded text, preserving the whole image with object-fit:contain.
Historical v32 replay remains intact. One focused Chromium regression reproduces
the natural-image overflow and verifies a 480px media frame keeps all text visible.
No thresholds, security, publication gates or retries changed. Only API and source/
generation worker restarted. A new sequential 15-page browser canary follows.
Known cumulative recorded cost **$6.413274**, with two earlier unknown billing outcomes.

## 15-page canary, iteration 26 — image fixed; final diagram label spills

Deck `deck_35ff0d825b50dae4`; operation `instantop_669d0271a306eef5`;
job `job_cf987060de15eeef`; attempt `instantattempt_80163f1329fb91a9`;
version `designver_4fe88af99e53dc034257f686`. One HTTP 200, 49,993 input /
18,451 output tokens, **$0.247001**. All 15 markers/OCR page 8 recovered,
zero thumbnails, eight compiled sections. The bounded OCR image slide now fits
and passes. Seven of eight isolated slides pass.

Slide 6 fails contrast for `body-06`, ratio 1: its Published label extends
beyond a squeezed 120-unit last diagram box onto the dark field. No canvas
overflow, missing image or other contrast failures. Screenshot confirms real
label spill; publication blocked and the browser shows failure at 253 seconds.
Small correction: prompt v34 specifies equal six-node widths and exact fitting
coordinates, including the final node, with readable short labels and safe
insets. One focused Chromium regression reproduces the failed 120-unit box
and verifies the 200-unit box preserves contrast/inset. Historical prompts
remain reconstructible. Only API/generation worker restarted. No retry policy
or render gates changed; a fresh sequential 15-page browser run follows.
Known cumulative recorded cost **$6.660275** plus two earlier unknown billing outcomes.

## 15-page canary, iteration 27 — complete local acceptance

Deck `deck_c83c8cb8f917842e`; operation `instantop_4b6846890d60c866`;
job `job_de7ad798b99ecf3c`; attempt `instantattempt_51facb8f5aad4de9`;
version `designver_dacd1f10bf6fe5738d2f7646`. One HTTP 200, 49,907 input /
18,991 output tokens, **$0.252294**. All 15 markers present; page 8 explicitly
`pdf_ocr`, its expected phrase and marker verified in persisted text. Zero
thumbnail jobs. Eight compiled slides, eight isolated proofs, publication pass.
Browser processing opens workspace at 235 seconds.

All eight browser slides and all eight exported PDF pages visually inspected.
OCR image/text fits completely; diagram labels fit; chart values correct; no
blank content, broken image, clipping, overlap or investor material. A crowded
looking table header was rechecked in the real browser: distinct cells, first
text right 390.69px, next text left 552.58px, so no overlap. Direct navigation,
refresh, slide selection and processing navigation pass; zero terminal polls.
Product Print / Save as PDF produces eight pages, **151,804 bytes**.
No further fix required. Known cumulative recorded cost **$6.912569** plus two
earlier unknown billing outcomes. Continue to one 20-page browser upload.

## 20-page canary, first run — caption target failure, then unknown repair outcome

Deck `deck_7c1dd69ee09dafd1`; operation `instantop_ea2ca92ac554dc52`;
job `job_a597ba8f737abdee`. All 20 source pages and markers persisted; pages 8
and 17 explicitly `pdf_ocr`, both expected phrases/markers verified; zero thumbnails.
First attempt `instantattempt_7f156cc3f998ab78`, provider
`req_01962b1deb96439ba7e5d5d59fb0b483`, HTTP 200, 61,695 input / 16,498 output
tokens, **$0.242099**. Eight returned sections fail `grounding_target_invalid`
on `figcaption`, section 7. The safe wrapper is not a manifest content target.

Second attempt `instantattempt_8dbb369c873dfe84` includes the exact structured
compiler failure, has a distinct envelope hash and reconstructs deterministically
with general intent. Its connection ends after about 246 seconds with TLS EOF;
response_state `transport_unknown`, no provider response ID/HTTP status/token
usage. Client request `9b65d59c-1cba-40f2-8ff9-557353cdf031`. **Two starts;
repair billing unknown.** No third attempt, compilation, proof, publication or export.
Browser displays terminal failure around 462 seconds.

Small correction: prompt v35 requests factual paragraphs inside figcaption with
exact fact references, rather than references on the wrapper itself. One focused
compiler regression reproduces the rejected wrapper and verifies its paragraph
keeps manifest/source lineage while invented claims remain rejected. Initial test
fixtures were corrected to avoid an unrelated ungrounded heading and to account
for the existing exact-text binding repair. No compiler/security/retry gates changed.
Only API/source-generation worker restarted before one new sequential 20-page run.
Known cumulative recorded cost **$7.154668**, now **three** unknown billing outcomes.

## 20-page canary, iteration 28 — repair blocked by a literal-only CSS check

Deck `deck_49cb6ddd1a01d717`; operation `instantop_f700bef837044274`;
job `job_1c3df5035e45d8f2`. All 20 source markers recovered with zero thumbnails.
First attempt `instantattempt_e8abfdcb1f88e15a`, HTTP 200, returns eight sections
and fails `grounded_fact_unknown`: several constructed block-based fact IDs
are absent from the supplied 149-fact catalog. Caption targets are corrected.
Repair `instantattempt_8a1766b63f27b482`, HTTP 200, returns 20 sections but is
rejected earlier in validation with `presentation_full_viewport_missing`.
Two requests, 124,372 input / 43,188 output tokens, **$0.587345**.
Exact recorded feedback, distinct repair envelope and deterministic reconstruction
verified. No third request, compiled artifact, proof, publication or export;
browser shows terminal failure at 483 seconds.

The repair defines :root{--section-min-h:100vh} and uses
.deck-section{min-height:var(--section-min-h)}. This is a valid full-viewport
composition, but the existing regex only accepts literal heights. Small correction:
validation v36 recognizes this direct root-token pattern, without guessing variable
fallbacks, cycles or ambiguous scopes. Historical v35 behavior remains intact;
provider prompt text is unchanged. Real browser proof is still mandatory.
One focused regression checks computed min-height=1080px in Chromium, accepts
the valid token and rejects missing/non-full-height tokens. Test fixture/version
arguments were corrected before the regression passed. Only API/generation worker
restarted before the next sequential 20-page browser canary.
Known cumulative recorded cost **$7.742013**, plus three earlier unknown billing outcomes.

## 20-page canary, iteration 29 — dense diagram/text clips the canvas

Deck `deck_12ef0b3880580aca`; operation `instantop_6caaa6c96431521e`;
job `job_7d55c58a2d839722`. One HTTP 200, attempt
`instantattempt_9d0fc81fbc9a0318`, 62,144 input / 17,850 output tokens,
**$0.256180**. All 20 source markers recovered, zero thumbnails. Compilation
passed with eight sections; isolated Chromium passed seven but rejected slide 3:
`overflowY=true`, clipped `headline-01` and `body-09`. The actual screenshot
confirms the heading and final bullet fall outside the canvas: a 420px diagram
was stacked above two dense text columns. No publication or export; browser
showed terminal failure at 315 seconds.

Small correction: prompt v37 budgets diagram, heading, padding and text together,
and requests a separate grounded section for dense details instead of clipping
or shrinking them. Existing render gates remain intact. One focused Chromium
regression reproduces overflow and verifies both separated compositions at the
same readable font sizes. Historical v36 token handling and prompt are preserved.
Only API/generation worker restart before one new sequential 20-page upload.
Known cumulative cost **$7.998193**, plus three unknown billing outcomes.

## 20-page canary, iteration 30 — response body interrupted in transport

Deck `deck_9ed40fe159ad6e46`; operation `instantop_e522a0b13418879f`;
job `job_1775b03b4c44ab6e`; attempt `instantattempt_a06c54a3b36c206f`;
client request `a152c95e-358e-4ee7-b776-7c27c29ca89e`. One generation start.
The body read raised `IncompleteRead(32768 bytes read, 55834 more expected)`
after approximately 223 seconds at the provider boundary. No complete response,
compiler result, proof, publication or export. Browser terminal at 264 seconds.
Both source OCR pages 8/17 have their expected text and markers; zero thumbnails.
Usage/billing is unknown, not zero: cumulative known cost remains $7.998193
plus **four** unknown outcomes. The old transport discarded the partial response
ID, so this terminal operation cannot be recovered from its persisted evidence.

Targeted transport correction: only the Instant caller opts into one GET of the
same stored response if an interrupted body begins with a valid response ID.
No POST replay, storage-policy change, replacement operation or extra generation
occurs within recovery. GET is capped at 30 seconds and the original remaining
deadline. Verify response ID/model and retain normal status parsing, accounting,
compilation and render gates. Missing ID, expired deadline, failed retrieval or
mismatched output fails closed with a redacted, non-retryable transport error.
Record original/request-retrieval IDs and retrieval count without partial content.
One focused mocked transport regression verifies these bounds; no paid test call.
Official API supports [retrieving a stored response](https://developers.openai.com/api/reference/python/resources/responses/methods/retrieve);
[storage defaults to true when omitted](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), as in the existing request.
Only API/generation worker restart before the next sequential browser upload.

## 20-page canary, iteration 31 — repair passes, repeated footer inventory clips

Deck `deck_c4854e4042cce3b5`; operation `instantop_faaf61e3ed2df930`;
job `job_79255ca5e4625b4f`. First attempt `instantattempt_3672b4796d7de836`
returns HTTP 200 and fails `grounded_fact_unknown`: one SVG fact reference
is absent from the immutable 149-fact catalog. Repair `instantattempt_eeed819a29f30f40`
returns HTTP 200 and passes compilation, eight sections. Exact feedback, distinct
envelope hash and deterministic reconstruction verified. Two requests, 124,229
input / 33,999 output tokens, **$0.495276**.

Isolated Chromium passes seven slides but rejects slide 3: overflowY=true, clipped
headline-01/body-09. Screenshot shows four repeated pipeline page headings and
five Expected marker footers beneath its large diagram. No publication/export.
Browser session expires during observation (~375 seconds); same account signs
back in and the same operation truthfully shows terminal failure. No upload replay.

Small prompt v38 correction: consolidate repeated substantive claims with all
supporting fact/page references; source coverage does not require printing every
header/footer/marker beside each visual. Unique substantive evidence remains
required; contextual markers may remain where relevant. No source/catalog rows
are removed and ingestion still verifies every extracted marker. One focused
compiler regression proves five sources retain evidence coverage through one
shared claim without repeating their footer inventory. No validation gate change.
Only API/generation worker restart before one fresh sequential 20-page upload.
Known cumulative cost **$8.493469**, plus four unknown billing outcomes.

## 20-page canary, iteration 32 — non-specific fact diagnostics defeat repair

Deck `deck_0db5485e7d7c9176`; operation `instantop_406380528c23c044`;
job `job_6634342c2dce9820`. Both requests return HTTP 200 and eight sections;
both fail `grounded_fact_unknown`. First `instantattempt_f3929a1dae25a4b6`
uses invalid paragraph/SVG references in section 6. Repair
`instantattempt_a66133e960c214e8` uses a constructed 16-hex block-based ID
on three table cells in section 4 instead. The saved diagnostic names only
the rule, giving neither invalid IDs nor element/section locations. Exact
feedback and distinct hashes are verified, but the feedback is insufficiently
actionable. Two starts, 124,978 input / 37,655 output tokens, **$0.532773**.
No compilation/proof/publication/export; terminal UI at 689 seconds.

Small compiler v29 correction: enumerate the current section's invalid references
with exact bounded IDs, tags and section ordinal in structured diagnostics.
Request two preserves these exact issues. It directs the model to copy supplied
fact IDs rather than construct/truncate block IDs. No fuzzy binding or grounding
bypass. v28 retains its original diagnostics and intent-bound artifact decoder.
One focused regression covers actual compiler issues through deterministic repair
and historical v28 behavior; the existing palette/intent regression also passes.
All four affected backend processes restart together for the compiler version;
frontend stays running. Known cumulative cost **$9.026242**, plus four unknown outcomes.

## 20-page canary, iteration 33 — repair reconstructs the deck and introduces invalid SVG

Deck `deck_edd3b88bf94a0dd7`; operation `instantop_9997a9062b4cf0cb`;
job `job_944248b99bbd9957`. First attempt `instantattempt_1c6fb9d36f5a69de`
returns seven sections, HTTP 200, then fails an unknown fact reference on section
2's paragraph/span. New exact ID/tag/section diagnostics are recorded and verified
in repair `instantattempt_0a917ec58ac6e34a`, which returns eight sections but
introduces a dummy SVG rectangle with height=-1 in section 4. It fails
`svg_rect_geometry_invalid` before later validation. Two requests, 124,425 input /
40,430 output tokens, **$0.559832**. No compilation/proof/publication/export;
terminal UI at 516 seconds.

Observed repair gap: v2 supplies source context and diagnostics but not the first
HTML. Small repair contract v3 now includes the verified encrypted first-response
checkpoint and its SHA-256, instructing edits limited to the reported failures
while preserving valid structure/geometry. The complete corrected HTML still
passes ordinary parsing, grounding, compilation and browser proof. v1/v2 exact
recovery remains supported. Input-byte/token/deadline checks run on the enlarged
repair body before a provider start. Missing/oversized checkpoint fails closed.

One focused regression verifies unchanged prior HTML, exact diagnostics, distinct
request hash, deterministic reconstruction and tamper-sensitive response hash.
A real local PostgreSQL/checkpoint check confirms its audited read uses a separate
connection and preserves the caller's transaction/advisory lock. No provider call
for this verification. Only API/generation worker restart before the next run.
Known cumulative recorded cost **$9.586074**, plus four unknown outcomes.

## 20-page canary, iteration 34 — complete local acceptance

Deck `deck_e8f59eb3a461cfea`; operation `instantop_bf3a84b9de6123e6`;
job `job_fc68d278941518e3`; published version `designver_3edf082572385dc5bb9a55c5`.
First attempt `instantattempt_9be3a4fac0a92f4c` returned HTTP 200 but failed five
`svg_rect_geometry_invalid` issues in section 4 (negative bar heights). Repair
`instantattempt_1667b417c63bc203` received the exact recorded diagnostics and
verified first HTML under repair v3, then passed compilation and all eight isolated
Chromium proofs. Publication completed and processing opened the workspace at
425 seconds. No additional code change or provider request followed this result.

Two generation starts, 134,148 input / 26,048 output tokens, **$0.428165** recorded.
First envelope `c974cc39ada5b911803c7c0da6858cfeaee37a53df255c470b48251b51932705`;
repair envelope `eccd7d5422771a52536baa051e1a2afb494a37e6316d35e25445868e4ccfa350`.
Actual production binding recovery verified deterministic reconstruction including
the exact first HTML and structured errors. Twenty contiguous source records and
markers, OCR pages 8/17 and zero thumbnail jobs verified.

All eight browser slides and all eight exported PDF pages were visually inspected.
No clipping, overlap, broken image, blank content or inappropriate investor content.
Direct navigation, refresh, processing navigation and slide navigation passed.
Published state stopped polling (zero requests in 15 seconds). Print action opened
the isolated published print view; Chromium exported eight pages, 215,114 bytes,
1440 by 810 PDF points. The native operating-system print dialog was not automated.
Source text still mentions thumbnails/presigned transfer; those words describe the
synthetic PDF, not evidence of the actual application transport or dependencies.
These small files used the product's browser multipart upload route, not its
large-file presigned PUT route.

Private evidence: `backend/.artifacts/local-product-iteration-34/canary-20/`
(browser-acceptance, acceptance, database, OCR, repair verification, screenshots
and generated PDF). Raw provider HTML and sessions remain private and ignored.

Final local accounting audit: **37 operations, 54 generation starts, $10.014239
known recorded cost, four transport-unknown billing outcomes**, no active operation,
all operation request limits preserved. The four successful operations alone
recorded $1.088358. Unknown billing is not counted as zero. These are application
tariff estimates, not an OpenAI invoice; an $85 account ceiling was not configured
or verified by this local run. No further paid operation is needed for final review.
