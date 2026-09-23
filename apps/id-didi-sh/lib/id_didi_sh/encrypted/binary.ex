defmodule IdDidiSh.Encrypted.Binary do
  @moduledoc """
  Ecto type for values encrypted at rest via `IdDidiSh.Vault`.

  Loading decrypts, so anything reading this field off a struct gets plaintext.
  That is why credentials are rendered through explicit serializers rather than
  by dumping structs to JSON — see `IdDidiSh.Credentials.render/1`.
  """
  use Cloak.Ecto.Binary, vault: IdDidiSh.Vault
end
