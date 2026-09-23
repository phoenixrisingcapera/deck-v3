defmodule IdDidiSh.Vault do
  @moduledoc """
  Cloak vault for credentials lent by people to entities.

  AES-256-GCM. The key comes from `CREDENTIAL_ENCRYPTION_KEY` (32 raw bytes,
  base64-encoded) in production; dev and test fall back to a fixed key so the
  suite needs no environment setup — that fallback is never reachable in prod
  because `init/1` raises without the env var there.

  **Recovery needs BOTH this key and the database.** Keep the key somewhere
  other than the database's own failure domain, or an outage becomes a
  permanent loss of credentials other people lent us.
  """

  use Cloak.Vault, otp_app: :id_didi_sh

  @impl GenServer
  def init(config) do
    config =
      Keyword.put(config, :ciphers,
        default: {Cloak.Ciphers.AES.GCM, tag: "AES.GCM.V1", key: key!(), iv_length: 12}
      )

    {:ok, config}
  end

  defp key! do
    case System.get_env("CREDENTIAL_ENCRYPTION_KEY") do
      nil ->
        if prod?() do
          raise """
          CREDENTIAL_ENCRYPTION_KEY is missing.

          Generate one with:

              openssl rand -base64 32

          Set it as a Fly secret AND store a copy outside Fly. Losing it makes
          every lent credential unrecoverable.
          """
        else
          # Deterministic dev/test key. Not a secret, and never used in prod.
          :crypto.hash(:sha256, "id-didi-sh-dev-credential-key")
        end

      encoded ->
        case Base.decode64(encoded) do
          {:ok, <<key::binary-32>>} ->
            key

          _ ->
            raise "CREDENTIAL_ENCRYPTION_KEY must be base64 of exactly 32 bytes (openssl rand -base64 32)"
        end
    end
  end

  defp prod?, do: Application.get_env(:id_didi_sh, :env) == :prod
end
