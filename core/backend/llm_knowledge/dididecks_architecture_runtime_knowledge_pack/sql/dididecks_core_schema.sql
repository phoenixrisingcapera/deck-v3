-- DidiDecks core schema blueprint
-- This is a planning/implementation starter, not a production migration.

CREATE TABLE dididecks_decks (
  id UUID PRIMARY KEY,
  workspace_id UUID NOT NULL,
  owner_user_id UUID NOT NULL,
  title TEXT NOT NULL,
  client_name TEXT,
  deck_type TEXT,
  status TEXT DEFAULT 'draft',
  brand_profile_id UUID,
  current_version_id UUID,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_slides (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  slide_number INTEGER NOT NULL,
  slide_key TEXT NOT NULL,
  title TEXT NOT NULL,
  slide_type TEXT NOT NULL,
  layout_key TEXT,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_slide_variants (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  slide_id UUID NOT NULL REFERENCES dididecks_slides(id) ON DELETE CASCADE,
  variant_key TEXT NOT NULL,
  variant_label TEXT,
  component_key TEXT,
  is_default BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_blocks (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  slide_id UUID NOT NULL REFERENCES dididecks_slides(id) ON DELETE CASCADE,
  variant_id UUID REFERENCES dididecks_slide_variants(id) ON DELETE CASCADE,
  block_key TEXT NOT NULL,
  block_type TEXT NOT NULL,
  content_json JSONB NOT NULL DEFAULT '{}',
  style_json JSONB NOT NULL DEFAULT '{}',
  position_json JSONB NOT NULL DEFAULT '{}',
  data_binding_key TEXT,
  is_locked BOOLEAN DEFAULT false,
  is_generated BOOLEAN DEFAULT false,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_persistent_fields (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  field_key TEXT NOT NULL,
  field_label TEXT NOT NULL,
  field_group TEXT NOT NULL,
  field_type TEXT NOT NULL,
  value_json JSONB NOT NULL DEFAULT '{}',
  source TEXT DEFAULT 'manual',
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(deck_id, field_key)
);

CREATE TABLE dididecks_field_usages (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  persistent_field_id UUID NOT NULL REFERENCES dididecks_persistent_fields(id) ON DELETE CASCADE,
  slide_id UUID NOT NULL REFERENCES dididecks_slides(id) ON DELETE CASCADE,
  variant_id UUID REFERENCES dididecks_slide_variants(id) ON DELETE CASCADE,
  block_id UUID NOT NULL REFERENCES dididecks_blocks(id) ON DELETE CASCADE,
  usage_type TEXT NOT NULL,
  transform_rule TEXT,
  is_required BOOLEAN DEFAULT false,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(persistent_field_id, block_id)
);

CREATE TABLE dididecks_change_requests (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  requested_by_user_id UUID NOT NULL,
  change_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_change_request_items (
  id UUID PRIMARY KEY,
  change_request_id UUID NOT NULL REFERENCES dididecks_change_requests(id) ON DELETE CASCADE,
  persistent_field_id UUID REFERENCES dididecks_persistent_fields(id),
  field_key TEXT,
  old_value_json JSONB NOT NULL DEFAULT '{}',
  new_value_json JSONB NOT NULL DEFAULT '{}',
  impact_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_rebuild_jobs (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  change_request_id UUID REFERENCES dididecks_change_requests(id),
  status TEXT NOT NULL DEFAULT 'queued',
  rebuild_scope TEXT NOT NULL,
  total_slides INTEGER DEFAULT 0,
  processed_slides INTEGER DEFAULT 0,
  error_message TEXT,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_deck_versions (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  version_number TEXT NOT NULL,
  created_by_user_id UUID NOT NULL,
  source_change_request_id UUID REFERENCES dididecks_change_requests(id),
  snapshot_json JSONB NOT NULL,
  summary TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(deck_id, version_number)
);

CREATE TABLE dididecks_audit_log (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  user_id UUID,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  action TEXT NOT NULL,
  before_json JSONB,
  after_json JSONB,
  metadata_json JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dididecks_exports (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  version_id UUID REFERENCES dididecks_deck_versions(id),
  export_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  file_url TEXT,
  error_message TEXT,
  created_by_user_id UUID NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  completed_at TIMESTAMP
);

CREATE TABLE dididecks_share_links (
  id UUID PRIMARY KEY,
  deck_id UUID NOT NULL REFERENCES dididecks_decks(id) ON DELETE CASCADE,
  version_id UUID REFERENCES dididecks_deck_versions(id),
  token TEXT NOT NULL UNIQUE,
  access_level TEXT DEFAULT 'view',
  expires_at TIMESTAMP,
  is_active BOOLEAN DEFAULT true,
  created_by_user_id UUID NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
