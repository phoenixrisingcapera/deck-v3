defmodule IdDidiSh.Accounts.LoginToken do
  use Ecto.Schema

  schema "login_tokens" do
    field :kind, :string
    field :token_hash, :binary
    field :email, :string
    field :didi_id, :string
    field :org_id, :string
    field :entity_id, :string
    field :role, :string
    field :app_slug, :string
    field :next_path, :string
    field :issued_by, :string
    field :expires_at, :utc_datetime
    field :claimed_at, :utc_datetime
    timestamps(type: :utc_datetime)
  end
end
