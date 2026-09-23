defmodule IdDidiSh.Repo.Migrations.CreateCredentials do
  use Ecto.Migration

  # Credentials are LENT by people to entities. An entity never owns one — the
  # owner keeps title throughout, and takes the key with them when they go.
  # See ai-labs/context-v/specs/
  # Flexible-Entity-Relationships-to-Mirror-Messy-IRL-Collaboration.md, Ruling 2.

  def change do
    create table(:credentials, primary_key: false) do
      add :id, :string, primary_key: true
      # The PERSON. Never an entity — that is the whole model.
      add :owner_didi_id,
          references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
          null: false

      add :provider, :string, null: false
      add :label, :string, null: false
      add :value_encrypted, :binary, null: false
      # Plaintext display hint only, so a human can tell two keys apart.
      add :last_four, :string, null: false
      add :revoked_at, :utc_datetime
      timestamps(type: :utc_datetime)
    end

    create index(:credentials, [:owner_didi_id])

    # ONE lending act. A lender names several entities in one gesture (the
    # cascade); ending this row pulls the key from all of them at once.
    create table(:credential_cascades, primary_key: false) do
      add :id, :string, primary_key: true
      add :credential_id, references(:credentials, type: :string, on_delete: :delete_all),
        null: false

      # May NOT be a member of the targets — the person with the credit card is
      # frequently not on the project.
      add :lent_by, :string, null: false
      add :lent_at, :utc_datetime, null: false
      # The cap belongs here, not on the loan: it is the lender's total exposure
      # on one card, across everywhere they lent.
      add :spend_cap, :integer
      add :cap_period, :string
      add :expires_at, :utc_datetime
      add :wind_down_until, :utc_datetime
      add :ended_at, :utc_datetime
      timestamps(type: :utc_datetime)
    end

    create index(:credential_cascades, [:credential_id])

    # ONE targeted entity. Ends with its cascade, or on its own (partial
    # withdrawal, for when one collaboration sours and the others do not).
    create table(:credential_loans, primary_key: false) do
      add :id, :string, primary_key: true
      add :cascade_id, references(:credential_cascades, type: :string, on_delete: :delete_all),
        null: false

      add :entity_id, references(:entities, type: :string, on_delete: :delete_all), null: false
      add :ended_at, :utc_datetime
      timestamps(type: :utc_datetime)
    end

    create unique_index(:credential_loans, [:cascade_id, :entity_id])
    create index(:credential_loans, [:entity_id])

    # Append-only. This is the lender's evidence of what their card paid for and
    # for whom — the thing that makes leaving a key in place a reasonable act
    # rather than an act of faith. Never updated, never deleted.
    create table(:credential_usage) do
      add :credential_id, :string, null: false
      add :cascade_id, :string, null: false
      add :loan_id, :string, null: false
      add :entity_id, :string, null: false
      add :didi_id, :string
      add :app_slug, :string
      add :occurred_at, :utc_datetime, null: false
      add :units, :integer
      add :cost_estimate, :integer
      timestamps(type: :utc_datetime)
    end

    create index(:credential_usage, [:credential_id, :occurred_at])
    create index(:credential_usage, [:entity_id, :occurred_at])
  end
end
