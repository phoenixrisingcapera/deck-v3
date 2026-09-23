defmodule IdDidiSh.Credentials.Cascade do
  use Ecto.Schema

  @periods ~w(day month)

  @primary_key {:id, :string, autogenerate: false}
  schema "credential_cascades" do
    field :credential_id, :string
    field :lent_by, :string
    field :lent_at, :utc_datetime
    field :spend_cap, :integer
    field :cap_period, :string
    field :expires_at, :utc_datetime
    field :wind_down_until, :utc_datetime
    field :ended_at, :utc_datetime
    timestamps(type: :utc_datetime)
  end

  def periods, do: @periods
end
