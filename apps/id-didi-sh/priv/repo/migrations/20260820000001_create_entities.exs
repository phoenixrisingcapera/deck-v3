defmodule IdDidiSh.Repo.Migrations.CreateEntities do
  use Ecto.Migration

  # Entities are the flat tenancy primitive: organization / workspace / project
  # are LABELS, not levels. There is deliberately no parent_id — projects are
  # collaborations among many organizations, and a hierarchy makes that common
  # case unrepresentable. See ai-labs/context-v/specs/
  # Flexible-Entity-Relationships-to-Mirror-Messy-IRL-Collaboration.md, Ruling 1.

  def change do
    create table(:entities, primary_key: false) do
      add :id, :string, primary_key: true
      add :kind, :string, null: false
      add :slug, :string, null: false
      add :name, :string, null: false
      # Descriptive only — grouping and breadcrumbs. NEVER consulted when
      # resolving access or credentials.
      add :org_id, :string
      timestamps(type: :utc_datetime)
    end

    create unique_index(:entities, [:slug])
    create index(:entities, [:kind])

    create table(:entity_memberships) do
      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
        null: false

      add :entity_id, references(:entities, type: :string, on_delete: :delete_all), null: false
      add :role, :string, null: false
      add :granted_by, :string
      # invite | auto_join | seed — so an audit can answer HOW someone got in.
      add :via, :string, null: false
      timestamps(type: :utc_datetime)
    end

    # Each membership row is independent. Removing a person from one entity
    # never touches their membership in another (Ruling 1b). The FK cascade
    # above is entity-deletion only — ordinary referential integrity.
    create unique_index(:entity_memberships, [:didi_id, :entity_id])
    create index(:entity_memberships, [:entity_id])
  end
end
