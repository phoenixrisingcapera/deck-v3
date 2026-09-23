defmodule IdDidiSh.Repo.Migrations.UserEmailAliases do
  use Ecto.Migration

  # Alt emails: one person, one didi_id, many addresses. A magic link to
  # any alias authenticates the same identity — the fullstack-vc
  # multi-email-person lesson, normalized from the start instead of
  # merge-chained after the fact. Uniqueness is DB-enforced across the
  # aliases table; cross-table collision with users.primary_email is
  # enforced at the context layer.

  def change do
    create table(:user_emails) do
      add :didi_id, references(:users, column: :didi_id, type: :string, on_delete: :delete_all),
        null: false

      add :email, :string, null: false
      timestamps(type: :utc_datetime)
    end

    create unique_index(:user_emails, ["lower(email)"], name: :user_emails_email_index)
    create index(:user_emails, [:didi_id])
  end
end
