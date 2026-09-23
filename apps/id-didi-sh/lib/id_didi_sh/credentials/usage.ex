defmodule IdDidiSh.Credentials.Usage do
  use Ecto.Schema

  schema "credential_usage" do
    field :credential_id, :string
    field :cascade_id, :string
    field :loan_id, :string
    field :entity_id, :string
    field :didi_id, :string
    field :app_slug, :string
    field :occurred_at, :utc_datetime
    field :units, :integer
    field :cost_estimate, :integer
    timestamps(type: :utc_datetime)
  end
end
