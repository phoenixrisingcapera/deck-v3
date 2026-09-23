defmodule IdDidiSh.Repo.Migrations.IdentitySchema do
  use Ecto.Migration

  # The full identity schema per the spec (ai-labs/context-v/specs/
  # Id-Didi-Sh-Identity-Service.md). The walking skeleton only *wires*
  # users + login_tokens + sessions + auth_events; orgs/memberships/
  # oauth_accounts/apps exist from day one so later increments are
  # data-shape ready.

  def change do
    create table(:users, primary_key: false) do
      add :didi_id, :string, primary_key: true
      add :primary_email, :string, null: false
      add :name, :string
      add :handle, :string
      add :avatar_url, :string
      add :last_seen_at, :utc_datetime
      timestamps(type: :utc_datetime)
    end

    create unique_index(:users, ["lower(primary_email)"], name: :users_primary_email_index)

    create table(:organizations, primary_key: false) do
      # id is the canonical email domain — the locked domain-as-id convention.
      add :id, :string, primary_key: true
      add :slug, :string, null: false
      add :name, :string, null: false
      timestamps(type: :utc_datetime)
    end

    create unique_index(:organizations, [:slug])

    create table(:firm_profiles, primary_key: false) do
      add :org_id, references(:organizations, type: :string, on_delete: :delete_all),
        primary_key: true

      add :firm_kind, :string
      add :data, :map
      timestamps(type: :utc_datetime)
    end

    create table(:memberships) do
      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
        null: false

      add :org_id, references(:organizations, type: :string, on_delete: :delete_all), null: false

      add :role, :string, null: false
      timestamps(type: :utc_datetime)
    end

    create unique_index(:memberships, [:didi_id, :org_id])

    create table(:oauth_accounts) do
      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
        null: false

      add :provider, :string, null: false
      add :provider_uid, :string, null: false
      add :profile, :map
      timestamps(type: :utc_datetime)
    end

    create unique_index(:oauth_accounts, [:provider, :provider_uid])

    create table(:login_tokens) do
      # kind: "magic_link" | "invite" — same table, same single-use
      # semantics, different delivery (the Fork 4 insight).
      add :kind, :string, null: false
      add :token_hash, :binary, null: false
      add :email, :string, null: false
      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all)
      add :org_id, :string
      add :role, :string
      add :app_slug, :string
      add :next_path, :string
      add :issued_by, :string
      add :expires_at, :utc_datetime, null: false
      add :claimed_at, :utc_datetime
      timestamps(type: :utc_datetime)
    end

    create unique_index(:login_tokens, [:token_hash])

    create table(:sessions, primary_key: false) do
      add :id, :string, primary_key: true

      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
        null: false

      add :expires_at, :utc_datetime, null: false
      add :last_seen_at, :utc_datetime
      add :revoked_at, :utc_datetime
      add :user_agent, :string
      add :ip, :string
      timestamps(type: :utc_datetime)
    end

    create index(:sessions, [:didi_id])

    create table(:auth_events) do
      add :occurred_at, :utc_datetime, null: false
      add :didi_id, :string
      add :app_slug, :string
      add :org_id, :string
      add :event_type, :string, null: false
      add :payload, :map
    end

    create index(:auth_events, [:didi_id, :occurred_at])

    create table(:apps, primary_key: false) do
      add :slug, :string, primary_key: true
      add :name, :string, null: false
      add :redirect_prefixes, {:array, :string}, default: []
      add :enabled, :boolean, default: true, null: false
      timestamps(type: :utc_datetime)
    end
  end
end
