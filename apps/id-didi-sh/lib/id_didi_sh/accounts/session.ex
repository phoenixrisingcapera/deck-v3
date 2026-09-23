defmodule IdDidiSh.Accounts.Session do
  use Ecto.Schema

  @primary_key {:id, :string, autogenerate: false}
  schema "sessions" do
    field :didi_id, :string
    field :expires_at, :utc_datetime
    field :last_seen_at, :utc_datetime
    field :revoked_at, :utc_datetime
    field :user_agent, :string
    field :ip, :string
    timestamps(type: :utc_datetime)
  end
end
