defmodule IdDidiSh.Entities.EntityMembership do
  use Ecto.Schema

  # Role vocabulary is shared with Accounts.Membership deliberately — one
  # lattice across org-wide and entity-scoped roles until something forces a
  # split (plan OQ 2).
  @vias ~w(invite auto_join seed)

  schema "entity_memberships" do
    field :didi_id, :string
    field :entity_id, :string
    field :role, :string
    field :granted_by, :string
    field :via, :string
    timestamps(type: :utc_datetime)
  end

  def vias, do: @vias
end
