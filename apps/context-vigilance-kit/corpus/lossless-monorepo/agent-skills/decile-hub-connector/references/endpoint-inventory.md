---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/decile-hub-connector/references/endpoint-inventory.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/decile-hub-connector/references/endpoint-inventory.md"
---

# Decile Hub API v1 — Endpoint Inventory

Exhaustive list of every path in the OpenAPI spec, grouped by `tags`. Generated from
`ai-labs/augment-it/clients/humain-vc/inputs/decilehub/202506_decilehub-docs_swagger.yaml`
(OpenAPI 3.0.1, `Decile Hub API v1`, 11,970 lines). Format:

`METHOD /path` — purpose — params — request body — response.

All routes are under the per-tenant base URL `https://<tenant>.decilehub.com`. Auth: `Authorization: <raw-token>`.
Operations marked **[agent-tool]** carry `x-agent-tool: true` in the spec (expose these first in the MCP).

## Authentication
- `GET /api/v1/whoami` — identify the authenticated token (kind, user, account, `account_user.roles`, `accessible_pipeline_ids`). 403 on legacy tokens.

## Admin
- `GET /api/v1/admin/accounts` — list accounts the calling admin can access. Query `search`; requires `X-Account-Id` header; admin token only.

## Accounts
- `GET /api/v1/accounts` — current account basic info.

## AccountUsers
- `GET /api/v1/account_users` — list team members (discover `assigned_id` for ownership). Query `page` (0-idx, size 100). Pattern A.

## ActivityEntries
- `GET /api/v1/activity_entries` — activity feed, newest first. Many filters (`subject_type`, `subject_id`, `event`, `user_id`, `created_after/before`, `page_token`, `per_page`≤100). Pattern C (`next_page_token`, `has_more`).
- `GET /api/v1/activity_entries/{id}` — single entry + full entryable body → `ActivityEntryDetail`.

## Entities (funds, SPVs, holdings, management companies, general partnerships)
- `GET /api/v1/entities` — list firm-admin entities. Query `type[]` (fund/spv/management_company/general_partnership/holding), `active`, `page` (1-idx), `per_page`. Pattern B.
- `POST /api/v1/entities` — create entity (+ Organization + FundDetail). Body `EntityCreateRequest`. **Not idempotent.** Requires full-access account admin.
- `GET /api/v1/entities/{id}` — show entity + details (+ optional `include=calculations`, `window=now|lifetime`).
- `PATCH /api/v1/entities/{id}` — update writable fields (`kind` immutable). Body `EntityUpdateRequest`. 409 if org shared with siblings.

## Capital Accounts
- `GET /api/v1/entities/{entity_id}/capital_accounts` — identity-only list. Query `active`, `partner_type`, `page`, `per_page`. Pattern B.
- `GET /api/v1/capital_accounts/{id}` — identity + commitments + contacts + entity (+ `include=transfers`).
- `GET /api/v1/capital_accounts/{id}/calculations` — single-CA period figures. Query `period_start`, `period_end`.
- `GET /api/v1/entities/{entity_id}/capital_accounts/calculations` — bulk calc + totals.

## Journal Entries (GL)
- `GET /api/v1/entities/{entity_id}/journal_entries` — list GL transactions (many filters). Pattern B.
- `POST /api/v1/entities/{entity_id}/journal_entries` — create one GL entry. **Not idempotent.**
- `POST /api/v1/entities/{entity_id}/journal_entries/bulk` — atomic batch (1–100). 422 → `JournalEntryBulkErrors`.
- `GET /api/v1/journal_entries/{id}` — show one.

## Accounting Accounts (chart of accounts)
- `GET /api/v1/accounting_accounts` — list GL codes (filters `code`, `code_prefix`, `is_1099_eligible`, `search`). Pattern B.
- `GET /api/v1/accounting_accounts/{id}` — show one.

## Capital Calls
- `GET /api/v1/capital_calls` — list. Query `entity_id` (**required**), `status`, `period_start/end`. Pattern B.
- `GET /api/v1/capital_calls/{id}` — header for one call.
- `GET /api/v1/capital_calls/{id}/details` — per-LP rows.

## Financial Reports
- `GET /api/v1/financial_reports` — list report jobs. Pattern A.
- `POST /api/v1/financial_reports` — queue async report job (202). `report_types` enum or `all_reports`; `format` xlsx/pdf.
- `GET /api/v1/financial_reports/{id}` — job status (poll `status_url`).

## Events
- `GET /api/v1/events` — list events (filters `title`, `start_date`, `end_date`, `published`, `access_type`). Pattern A.
- `POST /api/v1/events` — create event (auto-creates pipeline + questionnaire).
- `GET /api/v1/events/{id}` — show event (by id or `unique_event_id`; `include=guests`).
- `PUT /api/v1/events/{id}` — update event.
- `DELETE /api/v1/events/{id}` — delete event + associated data.
- `POST /api/v1/events/{id}/guests` — bulk-add guests (creates People). Returns `{added, duplicates, errors}`.
- `GET /api/v1/events/{id}/guests` — list guests w/ RSVP + stage.
- `PATCH /api/v1/events/{id}/rsvp` — update guest RSVP (`email`, `status`).

## Files & Folders
- `GET /api/v1/files` — list files (filters `name`, `folder_id`, `extension`, dates). Pattern A.
- `POST /api/v1/files` — upload (multipart). `file[file]`, `file[attachable_type]` (Person/Organization/PipelineProspect), `file[attachable_id]`, `folder_id`.
- `GET /api/v1/files/{id}` — show file.
- `PUT /api/v1/files/{id}` — update metadata or upload new version (multipart).
- `GET /api/v1/files/{id}/download` — download (binary).
- `POST /api/v1/files/{id}/save_to_folder` — save an in-message Attachment into a data-room folder (idempotent). *(not [agent-tool])*
- `GET /api/v1/folders` — list folders.
- `POST /api/v1/folders` — create folder (`name`, `parent_id`).
- `GET /api/v1/folders/{id}` — show folder + children (`contents` filter).
- `GET /api/v1/folders/search` — search folders by name. Query `q` (**required**). *(not [agent-tool])*

## Directory — People & Organizations (the CRM core)  [agent-tool]
- `GET /api/v1/organizations` — list orgs. `include` (notes,people,referred_by,…), `fields`, `custom_data_points`, `name`, dates, `page` (0-idx). Pattern A.
- `POST /api/v1/organizations` — **bulk** add orgs (first 100). → `{created, duplicates, errors}`.
- `POST /api/v1/organization` — **upsert ONE** org (natural key `name`). → `{status, organization_id, changes}`.
- `GET /api/v1/organizations/{id}` — show org (+ `logo` = `attached_image`).
- `POST /api/v1/organizations/{id}/notes` — append note (`body`, `context`).
- `GET /api/v1/people` — list people. `include` (notes,referred_by,organizations), `fields`, `custom_data_points`, `first_name`, `last_name`, `email`, dates, `page`. Pattern A.
- `POST /api/v1/people` — **bulk** add people (first 100). → `{created, duplicates, errors}`.
- `POST /api/v1/person` — **upsert ONE** person (natural key `email`). → `{status, person_id, changes}`.
- `GET /api/v1/people/{id}` — show person (+ `picture` = `attached_image`).
- `POST /api/v1/people/{id}/notes` — append note.

## Tasks
- `GET /api/v1/tasks` — list (requires `:hub_tasks` flag, else 404). Filters `status`, `assignee_id`, `origin`. Pattern A.
- `POST /api/v1/tasks` — create user-origin task (`title`, `assignee_id` required).
- `GET /api/v1/tasks/{id}` — get one.
- `PATCH /api/v1/tasks/{id}` — update.
- `POST /api/v1/tasks/{id}/complete` — mark completed.

## PipelineProspects (CRM deal/relationship rows)  [agent-tool]
- `GET /api/v1/pipeline_prospects` — list. `pipeline_id` (**required**), many filters (stage, tags, contact dates), `page`. Pattern A. (`x-agent-category: context`)
- `POST /api/v1/pipeline_prospects` — bulk create Person/Org prospects (first 100 each).
- `PATCH /api/v1/pipeline_prospects` — batch update (resolve by id/name/email). Partial success → 200 with `errors[]`.
- `PATCH /api/v1/pipeline_prospects/{id}` — update one (query `pipeline_id` required). **Returns bare `{error: string}` on failure.**
- `POST /api/v1/pipeline_prospects/{pipeline_prospect_id}/notes` — append note.
- `POST /api/v1/pipeline_prospect` — **upsert ONE** prospect (exactly one of person|organization). → `{status, pipeline_prospect_id, changes}`.
- `GET /api/v1/pipeline_prospects/{id}/action_executions` — list queued/run pipeline actions (tree).
- `POST /api/v1/pipeline_prospects/{id}/action_executions/{id}/execute` — execute one action.
- `POST /api/v1/pipeline_prospects/{id}/action_executions/{id}/preview` — preview a pending send_email action.

## Pipelines
- `GET /api/v1/pipelines` — list active pipelines (filter `kind`). (`x-agent-category: context`)
- `GET /api/v1/pipelines/{id}` — pipeline + stages.
- `GET /api/v1/pipelines/{id}/metrics` — current + 7-day-ago snapshot.
- `POST /api/v1/pipelines/{pipeline_id}/data_points` — create a custom data point (Variable) for the pipeline TYPE (account-wide fan-out; account admin). Format enum: string, paragraph, url, number, date, date_us, currency_us, currency_eu, percent, percent_rounded, select, file_url.

## ResearchInvestors (shared Decile Research LP roster)  *(not [agent-tool])*
- `GET /api/v1/research/investors` — list shared LP roster.
- `POST /api/v1/research/investors/copy_to_pipeline` — copy entries to a stage (202).

## Deal Shares (network feed)
- `POST /api/v1/deals/share` — create/update deal share (idempotent per org). Required: `organization_id, company_name, the_bet, referring_manager_name, referring_manager_email`.
- `GET /api/v1/deals/shares` — list own deal shares. Pattern C.
- `GET /api/v1/deals/shares/{id}` — get one.
- `DELETE /api/v1/deals/shares/{id}` — delete one.
- `POST /api/v1/deals/shares/{id}/copy_to_pipeline` — copy shared deal into a stage (202).
- `POST /api/v1/deals/shares/ai_auto_fill` — AI auto-fill enrichment (synchronous LLM).

## Deal Memos
- `GET /api/v1/deal_memos` — list (filters `organization_id`, `stage`). Pattern C.
- `POST /api/v1/deal_memos` — start a memo (`organization_id` required).
- `GET /api/v1/deal_memos/{id}` — full memo.
- `PATCH /api/v1/deal_memos/{id}` — update (422 if closed).
- `POST /api/v1/deal_memos/{id}/submit_for_review` — submit for review.
- `POST /api/v1/deal_memos/{id}/close` — close with `close_type` (approve/pass).

## PortfolioCompanies
- `GET /api/v1/portfolio_companies` — list (each = fund×org pair). Filters `fund_id`, `organization_id`. Pattern C.
- `GET /api/v1/portfolio_companies/{id}` — get one.
- `GET /api/v1/portfolio_companies/{portfolio_company_id}/investments` — list investment tranches.
- `GET /api/v1/portfolio_company_investments/{id}` — get one tranche.

## Pacts / Lpas
- `POST /api/v1/pacts/send_pact` — send PACT email to a Person (`person_id`, `pipeline_id`).
- `POST /api/v1/lpas/send_lpa` — send LPA email to a Person (moves to Closing, creates capital account).

## Emails
- `GET /api/v1/email_templates` — list templates. Pattern A.
- `GET /api/v1/email_templates/{id}` — full template + `variables: [{name, required}]` schema.
- `POST /api/v1/emails/preview` — preview templated/freeform email (exactly one recipient field).
- `POST /api/v1/emails` — send/schedule/test-send. Requires `confirm: true` (422 `confirmation_required` otherwise).

## Variables (merge-tag / data-point picker)  *(not [agent-tool])*
- `GET /api/v1/variables` — variable picker for `pipeline_id` (**required**). Pattern A.
- `GET /api/v1/variables/{id}` — show one variable (query `pipeline_id` required).

## Base (Decile Base community)
- `GET /api/v1/base/inbox` — inbox feed. Pattern D (`meta`).
- `GET /api/v1/base/channels` — list channels.
- `GET /api/v1/base/channels/{id}/posts` — posts in a channel.
- `POST /api/v1/base/posts` — create post (Markdown).
- `GET /api/v1/base/posts/{id}` — show post + replies.
- `POST /api/v1/base/replies` — reply to a post.
- `POST /api/v1/base/search` — full-text search posts + articles.
- `GET /api/v1/pipeline_prospects/{pipeline_prospect_id}/attachments` — list a prospect's files; merges `source: "direct"` (CRM attachments on the org/person) and `source: "questionnaire"` (founder's deal-intake uploads). 403 unless the pipeline is `investment`-type. **Not in the 202506 swagger — live docs only.**
- `POST /api/v1/pipeline_prospects/{pipeline_prospect_id}/attachments` — attach directly (multipart: `attachment[file]`, optional `attachment[name]`). No data-room copy. Needs `edit_prospects?`. **Live docs only.**
- `DELETE /api/v1/pipeline_prospects/{pipeline_prospect_id}/attachments/{attachment_id}` — delete a `direct` attachment only. **Live docs only.**
- `GET /api/v1/pipeline_prospects/{pipeline_prospect_id}/attachments/{signed_id}/download` — download by **signed blob id**. **Live docs only.**
- `GET /api/v1/base/attachments/{id}` — download a blob (binary / 302 if >50MB).

## agent_platform  *(not [agent-tool])*
- `POST /api/v1/agent_platform/file_search` — semantic search over account corpus (`q`, `limit`).

---

## Key schemas (field lists)

Full field lists for the CRM-core resources are in the SKILL.md "Pushing data" + "Mapping" sections.
The named component schemas worth knowing: `PortfolioCompany`, `PortfolioCompanyInvestment(Detail)`,
`Entity`/`EntityDetails` (funds), `CapitalAccountIdentity`/`Commitment`/`CapitalAccountContact`,
`Task`, `note_envelope`, `ActivityEntry(Detail)`, `DealShare`, `variable`, `attached_image`,
`associated_person`, `address`, `ErrorResponse`. **Person and Organization have NO standalone
schema** — their stored fields are dynamic (`data` / `custom_data_points` jsonb); the write fields
are documented inline (see SKILL.md). Read the spec for exact field-level detail.
