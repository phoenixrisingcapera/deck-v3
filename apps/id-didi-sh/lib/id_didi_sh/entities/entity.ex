defmodule IdDidiSh.Entities.Entity do
  use Ecto.Schema

  # kind is a DISPLAY LABEL. It confers no structure and no powers — an
  # "organization" entity is not a parent of a "project" entity, because there
  # are no parents. See Ruling 1.
  #
  # Because kinds are only labels, adding one is cheap and carries no schema or
  # access consequence — "team" is just another word people already use for a
  # group they collaborate in.
  @kinds ~w(organization workspace project team)

  @primary_key {:id, :string, autogenerate: false}
  schema "entities" do
    field :kind, :string
    field :slug, :string
    field :name, :string
    field :org_id, :string
    timestamps(type: :utc_datetime)
  end

  def kinds, do: @kinds
end
