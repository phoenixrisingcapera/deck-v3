defmodule IdDidiSh.Accounts.Membership do
  use Ecto.Schema

  @roles ~w(superuser org_owner org_admin editor viewer)

  schema "memberships" do
    field :didi_id, :string
    field :org_id, :string
    field :role, :string
    timestamps(type: :utc_datetime)
  end

  def roles, do: @roles
end
