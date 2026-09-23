defmodule IdDidiSh.Credentials.Credential do
  use Ecto.Schema

  @primary_key {:id, :string, autogenerate: false}
  schema "credentials" do
    # The owner is always a PERSON. There is no state in which an entity
    # "has" a credential the way it has a name.
    field :owner_didi_id, :string
    field :provider, :string
    field :label, :string
    # Decrypts on load. Never render a Credential struct directly — use
    # IdDidiSh.Credentials.render/1, which cannot leak this field.
    field :value_encrypted, IdDidiSh.Encrypted.Binary
    field :last_four, :string
    field :revoked_at, :utc_datetime
    timestamps(type: :utc_datetime)
  end
end
