# Live branding and quality test — 10 September 2026

## Release completed

Reviewed application commit: `2cc9b90358ccb220b884dc72f3ca25b68f781b44`, pushed to
`origin/main`. The LLM-first beta, quality integration, numerical/source fixes and
reliability work were already incorporated through `ad3b2c6`. Remaining older
planner/recovery branches contain superseded experiments; their recovered
capabilities remain available without activating a different beta architecture.

The new fix reads every page of the checksum-verified original PDF when optional
page-count metadata is missing. Supplied conflicting counts and checksum changes
remain blocking. Railway uploads now explicitly exclude `.local-work/`.

| Service | Deployment | Observed outcome |
| --- | --- | --- |
| API | `3988db3b-6e51-460e-88bf-de1f3d19c425` | MCP SUCCESS; runtime log reports release commit |
| Generation worker | `4870bce3-9a4c-470c-b6f2-b74ecc3e3419` | MCP SUCCESS; runtime log reports release commit |
| Render-proof worker | `e3d8bba0-6b87-4068-bd9c-aaa8de106f0e` | MCP SUCCESS; runtime log reports release commit |
| Isolated renderer | `211d8093-fbff-4769-abe5-f3615b06ea2e` | MCP SUCCESS; runtime log reports release commit |
| Frontend | `350a59bc-cad4-4451-969f-650f94bc0c51` | MCP SUCCESS; deployed from the clean release archive |

Live frontend: https://instantdeck.aistack.codes

## Checks and evidence limits

- Ten focused backend checks passed, including factual correction, immutable source
  binding, missing page-count handling, brand-palette preservation, upload website
  propagation and audience intent. Synthetic corrected content passed isolated
  Chromium rendering and PDF export.
- Five frontend reconciliation tests passed. Svelte checking reported zero errors
  and 16 existing warnings.
- Chromium authenticated the existing test account and reached the live upload page.
  Railway MCP supplied deployment and runtime-log verification; no browser MCP tool
  is available in this session.
- The original 14-page PDF was inspected locally for a future comparison: red
  typography, warm off-white backgrounds, distinctive large wordmarks and source
  photography are the brand reference. This is not a finding about new output.

## Live generation not started

Automatic approval review rejected the live upload command because it could send
the private source PDF to paid LLM processing without an explicit paid-verification
allowance. No upload marker, new operation or new provider request was created.
New LLM spend is $0. Deployment resource usage is not measured or included in that
figure. Historical paid attempts and unknown billing outcomes remain unchanged.

Requested allowance: one live test, $3 total provider spend, at most two designer
calls and two factual-review calls, with no additional test run. Approval is pending.
After approval, follow upload, extraction, brand extraction, design, factual review,
compilation, isolated render proof, publication and product PDF export. Assess
factual fidelity, readability, narrative, logo/wordmark, palette, typography and
source imagery against the original. A healthy deployment is not output acceptance.

Private screenshots, source reference, test scripts and deployment IDs remain in
ignored `.local-work/evidence/live-brand-test/`; sessions and source content are
excluded from this report and Git.

## Subsequent authorization and release correction

The approval-pending section above records the earlier state. The user subsequently
approved paid live testing and specified a $10 per-deck maximum. The first live
upload extracted all 14 source pages and received a designer response, then failed
factual review with no findings. It did not publish or export. Both provider calls
logged success; zero settled review cost is not evidence of zero billing. Historical
unknown costs and the failed operation remain unchanged.

General product fixes in `4bc34bd` now preserve exact source vector palette and
source typography over automatic website enrichment, skip the secondary beta brand
LLM, and supply one canonical application-owned brand contract to the designer.
Factual review has a larger bounded output allowance and now retains encrypted
received responses and settles known usage for typed unusable-response errors.
The old live failure subtype is not proven. Sixteen focused backend tests passed,
including isolated rendering. All four backend deployment IDs were read back as
SUCCESS using existing Railway CLI access after MCP OAuth expired.

Frontend `c9680fe` truthfully distinguishes incomplete review from actual reported
factual discrepancies and provides a workspace link. It is on `origin/main`;
deployment `6f200c6f-fb39-401e-b7e8-0bac3e1efdce` is SUCCESS. Svelte checking passed
with zero errors and 16 existing warnings. A fresh live upload-to-export test has
started. Successful deployment does not yet establish output-quality acceptance.
