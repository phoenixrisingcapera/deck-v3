defmodule IdDidiSh.Accounts.Organization do
  use Ecto.Schema

  # id is the canonical email domain — the locked domain-as-id convention
  # (lossless.group, humain.vc, …). slug is the human handle.
  @primary_key {:id, :string, autogenerate: false}
  schema "organizations" do
    field :slug, :string
    field :name, :string
    timestamps(type: :utc_datetime)
  end
end
