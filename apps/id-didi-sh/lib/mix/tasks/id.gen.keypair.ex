defmodule Mix.Tasks.Id.Gen.Keypair do
  @shortdoc "Generate an Ed25519 signing keypair; prints the private JWK for the env"

  @moduledoc """
  Generates a fresh Ed25519 keypair and prints:

  - the private JWK JSON — set as `ID_SIGNING_JWK` in the deploy host's
    secret store (NEVER commit it)
  - the public JWK — what /.well-known/jwks.json will serve

  Dev doesn't need this: with `allow_dev_keys: true` a dev keypair is
  auto-generated at priv/keys/dev_signing.jwk (gitignored).
  """

  use Mix.Task

  @impl true
  def run(_args) do
    jwk = JOSE.JWK.generate_key({:okp, :Ed25519})
    {_meta, private} = JOSE.JWK.to_map(jwk)
    {_meta, public} = jwk |> JOSE.JWK.to_public() |> JOSE.JWK.to_map()

    Mix.shell().info("""
    # Private JWK — set as ID_SIGNING_JWK (secret store only, never commit):
    #{Jason.encode!(private)}

    # Public JWK (served via JWKS; kid = #{JOSE.JWK.thumbprint(jwk)}):
    #{Jason.encode!(public)}
    """)
  end
end
