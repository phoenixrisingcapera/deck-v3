defmodule IdDidiSh.Repo.Migrations.AppTokens do
  use Ecto.Migration

  # `apps` was a registry for validating redirect prefixes. Resolving a lent
  # credential is server-to-server, so an app now needs to prove it is itself.
  # Same discipline as login_tokens: the raw token is shown once, only the
  # SHA-256 hash is stored. Nullable — existing apps have none and cannot call
  # resolve until one is issued.
  def change do
    alter table(:apps) do
      add :token_hash, :binary
      add :token_issued_at, :utc_datetime
    end

    create unique_index(:apps, [:token_hash])
  end
end
