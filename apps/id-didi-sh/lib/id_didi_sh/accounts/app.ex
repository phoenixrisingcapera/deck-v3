defmodule IdDidiSh.Accounts.App do
  use Ecto.Schema

  @primary_key {:slug, :string, autogenerate: false}
  schema "apps" do
    field :name, :string
    field :redirect_prefixes, {:array, :string}, default: []
    field :enabled, :boolean, default: true
    # Server-to-server credential. Hash only — the raw token is returned once
    # at issue time and never again.
    field :token_hash, :binary
    field :token_issued_at, :utc_datetime
    timestamps(type: :utc_datetime)
  end
end
