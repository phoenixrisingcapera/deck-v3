# Q7 Reliability Completion — 2026-07-22

## Status and scope

Q7 is complete on the canonical backend and mounted product frontend. This
record reconciles partial Smart Deck generation, failed-slide-only retry,
export safety, provider quotas and budgets, whole-operation deadlines,
terminal timeout handling, usage accounting, PostgreSQL concurrency evidence,
CI, release tags, Railway rollout, and the bounded paid acceptance.

This is a documentation-only closeout. It does not change routes, schemas,
persistence, migrations, workers, authentication, authorization, billing, or
provider configuration. Q8 backend PR #135 and frontend PR #110 are outside
Q7 and were not changed by this closeout.

## Product and route contracts

The canonical product prefix remains
`/api/products/deck-aistack-codes`. Existing authentication, deck ownership,
workspace boundaries, and idempotency checks remain authoritative.

### Exact generation coverage and export gating

- Generation persists ordered `requestedSlideIds`, `completedSlideIds`, and
  `failedSlideIds`, plus `coverageComplete` and `partialSuccess`.
- Requested IDs must be unique. Completed and failed IDs must each be unique,
  disjoint, non-empty, and together form the exact requested set.
- Partial results remain available for preview and review; successful slides
  are not discarded because another requested slide failed.
- Export rejects an explicitly incomplete active generated version with the
  stable error code `generation_coverage_incomplete` and next action
  `retry_failed_slides`.
- Complete results remain exportable. Legacy/source-only paths without the Q7
  coverage marker retain compatibility rather than being retroactively
  classified as incomplete.

### Failed-slide-only retry

- The authenticated command is
  `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/smart-deck-generation/retry-failed`.
- The backend derives the retry target only from the prior durable generation
  result's `failedSlideIds`; callers cannot substitute successful or arbitrary
  slide IDs.
- A retry requires explicit incomplete coverage and at least one persisted
  failed ID. Invalid partitions fail safely rather than regenerating the deck.
- The new workflow input selects only failed source slides and records the
  prior generation job. Its idempotency identity includes the prior job and
  caller key, preventing duplicate retry work while allowing a new operation.
- The mounted Smart Deck control and canonical frontend proxy landed in
  frontend PR #109. Successful slides and prior review artifacts are retained.

## Quotas, rate limits, and operation budgets

- Smart Deck generation and retry retain authenticated per-user request rate
  limits. The retry route is limited to five requests per hour; generation
  routes remain limited to ten per hour. Due Diligence remains limited to ten
  workflow requests per hour.
- AI generation quota enforcement remains a separate gate from request-rate
  limiting. `ai_usage_buckets` and `ai_budget_reservations` are owned by the AI
  database lineage; Core keeps only a no-op migration marker for the published
  history.
- Workers reserve an operation budget before provider work using a unique,
  idempotent reservation key. Reservation and bucket mutation occur atomically.
- Reconciliation is idempotent: terminal success, failure, or timeout records
  actual aggregate usage when available and cannot charge the same reservation
  twice.
- Generation (including critique/schema/repair calls), Smart Edit, and Due
  Diligence use the shared reservation/reconciliation contract. Provider
  adapters return typed usage; no provider response body is retained for Q7
  accounting.
- Concurrent reservation attempts are serialized by PostgreSQL constraints and
  row locking so accepted concurrent work cannot overspend the configured
  bucket. Reconciliation remains safe under concurrent or repeated completion.

## Whole-operation deadlines and `timed_out`

- An operation receives one absolute monotonic deadline. Each provider stage
  receives only the remaining time; critique, schema repair, validation repair,
  Smart Edit classification/generation/repair, and Due Diligence stages do not
  reset the operation clock.
- Deadline exhaustion stops further provider stages and is distinguished from
  generic provider or validation failure.
- Durable workflow jobs support terminal `timed_out`. Smart Edit persists a
  sanitized `timed_out` run state, and shared workflow/read models recognize it
  as terminal failure without exposing prompts or provider payloads.
- Budget reconciliation runs for timeout and failure paths and includes typed
  usage already reported by completed provider stages. Unknown usage is not
  invented.

## Usage accounting

- `LlmResponse.usage` carries provider-neutral aggregate input/output/total
  token counts and estimated cost when the adapter reports them.
- OpenAI, Anthropic, and OpenRouter response handling contributes aggregate
  usage without persisting request or response payloads.
- Generation, Smart Edit, and Due Diligence aggregate usage across their
  internal provider calls, including partial totals preceding timeout/failure,
  then reconcile the operation reservation once.
- Missing provider metrics remain absent. The paid acceptance report did not
  expose aggregate token/cost fields, so this record does not infer them.

## Verification and PostgreSQL proof

The Q7 closeout evidence recorded before publication was:

- 72 focused/adjacent tests passed, with two environment-gated skips.
- 24 focused deadline/timeout/usage-accounting tests passed during the final
  accounting slice.
- A real ephemeral PostgreSQL 16 test passed concurrent reservation and
  idempotent reconciliation (`tests/test_ai_budget_postgresql_concurrency.py`).
- App/test compilation, canonical backend, production contract, production
  workflow, production boundary, and diff checks passed.
- The broad 692-test run produced 648 passes, 22 skips, and 22 failures. Two
  Q7-caused mock-signature regressions were repaired; the remaining failures
  were classified as pre-existing environment/order-isolation families and
  did not invalidate the focused Q7 gates.
- For this documentation reconciliation, focused Q7 contract tests and
  canonical/production verifiers were rerun from a fresh fetched-main worktree,
  along with Markdown/diff checks.

## Pull requests, commits, CI, and tags

Fresh `gh` and `git` verification on 2026-07-22 confirmed every listed PR is
`MERGED`; every backend PR's required `deck-extractor-stack` check completed
successfully; each source and merge commit is an ancestor of the current
repository `origin/main`; and every listed annotated tag peels to its merge.
Frontend PR #109 reports no GitHub check runs in its PR metadata.

| Repository PR | Scope | Source | Merge | Completion tag |
|---|---|---|---|---|
| Backend #119 | exact coverage and export gate | `ab27353` | `804b555` | `adhd-finish-20260721-1850-generation-export-coverage` |
| Backend #124 | failed-slide-only retry | `49baf6a` | `7652e36` | `adhd-finish-20260722-q7-failed-slide-retry` |
| Backend #126 | atomic operation budgets | `153904f` | `cd3f3f4` | `adhd-finish-20260722-q7-operation-budgets` |
| Backend #127 | whole-operation deadlines | `691811a` | `a844448` | `adhd-finish-20260722-q7-operation-deadlines` |
| Backend #133 | mounted guardrail integration | `c502a0c` | `20e385a` | `adhd-finish-20260722-q7-provider-guardrails` |
| Backend #134 | provider usage/deadline closeout | `6370f51` | `980ad05` | `adhd-finish-20260722-q7-provider-closeout` |
| Frontend #109 | mounted failed-slide retry control | `4967c98` | `b61162e` | `adhd-finish-20260722-q7-failed-slide-retry-ui` |

The PR #126 rollout exposed migration ownership drift: a Core migration tried
to alter AI-owned budget tables. The follow-up migration correction was merged
separately in backend PR #130 (`370078b`) and deployed successfully before Q7
runtime completion. This preserved the published Core migration history while
placing schema ownership in the AI Alembic lineage.

## Railway evidence

Existing root ledgers and value-safe Railway CLI metadata were reconciled. No
environment variable values, credentials, prompts, deck contents, provider
responses, or private payloads were read into this record.

- After PR #133, API deployment `3173bd8a`, LLM worker deployment `588d911c`,
  and frontend deployment `c70a7a84` reached `SUCCESS`; API readiness and the
  frontend returned HTTP 200.
- Due Diligence deployment `9579c6c8-013a-408f-82e8-41968e216f85` reached
  `SUCCESS`; sanitized logs recorded `deck_worker_started` and no provider work
  was triggered by the verification.
- After PR #134, API deployment `7eb2df4c`, LLM worker deployment `e3888202`,
  and Due Diligence deployment `47e0bbe5` were recorded online. Health/product
  readiness returned HTTP 200 and worker startup was observed.
- Railway may later mark superseded deployments `REMOVED`; that lifecycle state
  does not negate their recorded successful rollout and health evidence.

## Paid acceptance outcome

Exactly one bounded paid full acceptance ran against backend merge `980ad05`.
It passed 144 local contracts, deployed health and authentication, upload and
four miniatures, real Smart Deck generation, and design apply. It then stopped
at the pre-existing Smart Edit boundary because the acceptance runner received
no immediate run/suggestion identity. The failure was classified as systemic,
so the authorized second paid run was not used.

This result accepts the Q7 reliability scope through generation and design
apply. It is not a claim that the later Smart Edit/Q8 journey passed. The
redacted acceptance evidence contained no aggregate token or cost values; none
are guessed here.

## Non-Q7 follow-ups

- Q8 owns the Smart Edit terminal polling/developer-envelope correction and
  later diagnostic telemetry/admin-boundary work. Q8 PRs #135/#110 are not
  part of this Q7 completion record.
- The repeated-generation source-readiness correction and later Smart Deck UI
  phases are separate follow-ups, not retroactive Q7 release requirements.
- Repository-wide test environment/order isolation remains follow-up work; it
  should not be hidden, but it was not caused by this documentation closeout.
- Self-service export and billing remain governed by the separate testing
  release policy; Q7's coverage gate does not activate either capability.
