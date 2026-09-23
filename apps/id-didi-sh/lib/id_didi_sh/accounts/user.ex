defmodule IdDidiSh.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:didi_id, :string, autogenerate: false}
  schema "users" do
    field :primary_email, :string
    field :name, :string
    field :handle, :string
    field :avatar_url, :string
    field :last_seen_at, :utc_datetime

    has_many :memberships, IdDidiSh.Accounts.Membership,
      foreign_key: :didi_id,
      references: :didi_id

    timestamps(type: :utc_datetime)
  end

  def changeset(user, attrs) do
    user
    |> cast(attrs, [:didi_id, :primary_email, :name, :handle, :avatar_url])
    |> validate_required([:didi_id, :primary_email])
    |> update_change(:primary_email, &String.downcase/1)
    |> validate_format(:primary_email, ~r/^[^@\s]+@[^@\s]+$/)
    |> unique_constraint(:primary_email, name: :users_primary_email_index)
  end
end
