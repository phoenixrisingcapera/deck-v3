defmodule IdDidiSh.Keys do
  @moduledoc """
  Ed25519 signing keypair management.

  Resolution order:

  1. `ID_SIGNING_JWK` env var — the private key as a JWK JSON string
     (production; injected by the deploy host's secret store).
  2. `priv/keys/dev_signing.jwk` — dev/test only (`allow_dev_keys: true` in
     the env config). Generated on first use; the directory is gitignored.

  Only this service ever holds the private key — consumers fetch the public
  half from `/.well-known/jwks.json`. The key id (`kid`) is the RFC 7638
  JWK thumbprint.
  """

  @dev_key_path Path.join(["priv", "keys", "dev_signing.jwk"])

  @doc "The private signing JWK (JOSE.JWK struct). Cached in :persistent_term."
  def signing_jwk do
    case :persistent_term.get({__MODULE__, :jwk}, nil) do
      nil ->
        jwk = load_or_generate()
        :persistent_term.put({__MODULE__, :jwk}, jwk)
        jwk

      jwk ->
        jwk
    end
  end

  @doc "The public JWK map (no private material), with kid + alg + use set."
  def public_jwk_map do
    {_meta, map} = signing_jwk() |> JOSE.JWK.to_public() |> JOSE.JWK.to_map()
    Map.merge(map, %{"kid" => kid(), "alg" => "EdDSA", "use" => "sig"})
  end

  @doc "JWKS document served at /.well-known/jwks.json."
  def jwks, do: %{"keys" => [public_jwk_map()]}

  @doc "RFC 7638 thumbprint of the signing key."
  def kid, do: JOSE.JWK.thumbprint(signing_jwk())

  defp load_or_generate do
    cond do
      jwk_json = System.get_env("ID_SIGNING_JWK") ->
        JOSE.JWK.from_map(Jason.decode!(jwk_json))

      dev_keys_allowed?() ->
        load_or_generate_dev_key()

      true ->
        raise """
        ID_SIGNING_JWK is not set and dev keys are not allowed in this
        environment. Generate a keypair with `mix id.gen.keypair` and set
        the env var.
        """
    end
  end

  defp dev_keys_allowed? do
    Application.get_env(:id_didi_sh, :identity, [])
    |> Keyword.get(:allow_dev_keys, false)
  end

  defp load_or_generate_dev_key do
    path = Application.app_dir(:id_didi_sh, @dev_key_path)

    if File.exists?(path) do
      JOSE.JWK.from_map(Jason.decode!(File.read!(path)))
    else
      jwk = JOSE.JWK.generate_key({:okp, :Ed25519})
      {_meta, map} = JOSE.JWK.to_map(jwk)
      File.mkdir_p!(Path.dirname(path))
      File.write!(path, Jason.encode!(map))
      jwk
    end
  end
end
