defmodule IdDidiSh.Credentials.Loan do
  use Ecto.Schema

  @primary_key {:id, :string, autogenerate: false}
  schema "credential_loans" do
    field :cascade_id, :string
    field :entity_id, :string
    field :ended_at, :utc_datetime
    timestamps(type: :utc_datetime)
  end
end
