# Instant Deck Customer/Admin Contract Audit

Date: 2026-08-24

## Conclusion

**C. Frontend-only stale reconciliation.**

The customer product does not call an admin-protected endpoint to load or
regenerate Instant Deck. Both the canonical workflow read and generation
command call `get_user_deck_or_404`. The Smart Deck workspace compatibility
read uses the same ownership dependency. Those routes do not branch their
response schema on `User.role`.

The first incorrect transition was in
`UserSmartDeckWorkspace.svelte`: `onMount()` began an authoritative workspace
reconciliation, but `instantCommandInFlight` was a non-reactive boolean and was
not included in the top-bar disabled state. An SSR-stale terminal snapshot
could therefore render an enabled **Regenerate** while the browser refresh was
already in progress. The click handler's first early return then suppressed
transport. No backend POST existed to authorize or reject.

The correction makes the shared reconciliation/submission mutex reactive and
includes it in every visible generation control. The top bar now shows a
disabled **Checking status...** state during the authoritative refresh. The
existing active-operation guard remains intact.

## Production owner evidence

Read-only browser requests were made through the real signed-in product at
`https://deck.aistack.codes` for persisted deck
`deck_dc8c7c205dd8d1d8`. Credentials and tokens were not recorded.

| Request | Owner result | Safe product truth |
| --- | ---: | --- |
| canonical workflow state | 200 | completed; no active operation |
| Smart Deck workspace | 200 | one completed Instant job; selected DesignVersion `designver_94f0ffb7315e832babe19b96`; 9 generated slides |
| deck graph | 200 | customer graph available |
| deck properties | 200 | customer properties available |
| workspace preferences | 200 | customer preferences available |
| iterations | 200 | compatibility iterations available |
| AI-provider summary | 200 | summary available; not needed for Regenerate readiness |
| developer tools | 200 | diagnostics available; not needed for Regenerate readiness |

No admin or super-admin credential was available in the workspace. Role
comparison below is therefore based on mounted authorization code and response
models, not an invented production login. A plain `admin` is intentionally not
a cross-tenant operator in `user_can_access_deck`; a non-owner receives 404.
`super_admin` may cross ownership for support, but the product handlers still
call the same read models and return the same response models.

## Role and route matrix

| Frontend caller | Endpoint | Mounted backend owner | Authorization and ownership | Owner | Admin on owner's deck | Super-admin | Schema/command impact |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `loadProcessingVisibility` | `GET /api/products/deck-aistack-codes/decks/{id}/workflow-state` | `deck_workflow_state` / `get_deck_workflow_state` | authenticated; `get_user_deck_or_404` | 200 | 404 unless owner | 200 | same `DeckWorkflowStateResponse`; mandatory mount gate |
| `refreshUserSmartDeckWorkspace` | `GET /api/decks/{id}/smart-deck` proxy to product backend | `smart_deck_workspace` / `get_smart_deck_workspace` | authenticated; `get_user_deck_or_404` | 200 | 404 unless owner | 200 | same `SmartDeckWorkspaceResponse`; mandatory command reconciliation |
| `startSmartDeckGenerationWorkflow` | `POST /api/products/deck-aistack-codes/decks/{id}/workflows/smart-deck-generation` | `start_smart_deck_generation_workflow` / `queue_smart_deck_generation` | authenticated owner; guardrail, rate limit, queue conflict | 202/409 | 404 unless owner | 202/409 | same accepted/conflict contract; no role-shaped readiness |
| page loader | `GET /api/decks/{id}` | deck graph route/read model | authenticated owner | 200 | 404 unless owner | 200 | required for mounted canvas, not active-operation truth |
| page loader | `GET /api/decks/{id}/properties` | deck properties route | authenticated owner | 200 | 404 unless owner | 200 | optional customer enhancement; fallback hides failure |
| page loader | `GET /api/decks/{id}/workspace` | preferences route | authenticated owner | 200 | 404 unless owner | 200 | optional customer enhancement; fallback hides failure |
| page loader | `GET /api/products/deck-aistack-codes/decks/{id}/workspace` | product workspace route | authenticated owner | 200 | 404 unless owner | 200 | legacy shell model; not command readiness |
| page loader | `GET /api/decks/{id}/iterations?limit=3` | iterations route | authenticated owner | 200 | 404 unless owner | 200 | legacy compatibility; failure degrades only |
| page loader | `GET /api/settings/workspace/ai-provider` | workspace provider summary | authenticated workspace owner | 200 | role does not grant workspace ownership | owner-dependent | administrative/provider enhancement; must not block command |
| source inspection | product deck/source reads | customer product routes | authenticated owner | 200 when persisted | 404 unless owner | 200 | optional inspection; failure degrades only |
| developer payload | `GET .../{id}/developer-tools` | `product_developer_tools` | authenticated owner | 200 | 404 unless owner | 200 | diagnostics only; does not drive command guard |
| failure reporting | `POST /api/support/failure-tickets/report` | support failure route | authenticated customer context | accepted | accepted in own context | accepted | reporting only; no readiness input |

## Loader classification

| Resource | Classification | May block mount? | May block Regenerate? |
| --- | --- | ---: | ---: |
| workflow state | mandatory customer Instant Deck data | yes, before readiness | indirectly, only through durable active/readiness truth |
| Smart Deck workspace/version/jobs/slides | mandatory customer Instant Deck data | yes | yes |
| deck graph | mandatory mounted canvas data | yes | only if source identity is unavailable |
| properties and preferences | optional customer enhancement | no | no |
| source inspection | optional customer enhancement | no | no |
| iterations/design batches | legacy compatibility data | no | no |
| product workspace shell model | legacy compatibility data | no | no |
| AI-provider summary | admin-era/provider enhancement | no | no |
| developer-tools payload | developer diagnostics | no | no |
| failure-ticket reporting | support diagnostics | no | no |
| unrelated Smart Deck assistant state | unrelated Smart Deck data | no | no |

## Early-return trace

| Boundary | Condition | Source | Transport? | Feedback after correction |
| --- | --- | --- | ---: | --- |
| top bar | reconciliation/submission mutex active | browser-local reactive mutex | no | disabled `Checking status...` |
| `regenerateInstantDeck` | generation already active or unresolved | canonical workspace jobs/status | no | `Check status` or generating status |
| `followActiveGeneration` | queued/running durable job | refreshed workspace response | no duplicate POST | follows job and displays progress |
| `followActiveGeneration` | lagging active hint without visible job | refreshed workspace response | no | resumable `Check status` message |
| source coverage | more than 25 pages | canonical source-slide list | no | visible error |
| command client | settled and source-ready | validated workspace | yes | 202 operation ID or visible 409 conflict |

## Target customer contract

The proposed `GET .../instant-deck` aggregate remains a sound future
simplification: it would combine source readiness, generation permission,
selected immutable version and version summaries. It is not required to correct
this incident, and introducing a new backend read model would be larger than the
proven frontend boundary defect. Provider credentials, prompts, embeddings and
control-plane configuration must remain excluded.
