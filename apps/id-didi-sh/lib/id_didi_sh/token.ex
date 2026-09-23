defmodule IdDidiSh.Token do
  @moduledoc """
  Mint and verify the `didi_session` cookie token.

  EdDSA (Ed25519)-signed JWT — asymmetric on purpose: consumers verify with
  the JWKS public key and can never mint (the invariant HS256 would break).
  Claims stay minimal (`sub` = didi_id, `sid` = session row id) — org/role
  context is fetched from `/api/me`, not baked into the token, so role
  changes propagate without waiting out a token TTL.
  """

  alias IdDidiSh.Keys

  @doc "Sign a session token. Returns the compact JWS string."
  def sign(didi_id, session_id, opts \\ []) do
    now = System.system_time(:second)
    ttl = Keyword.get(opts, :ttl_seconds, config(:token_ttl_seconds, 12 * 60 * 60))

    claims = %{
      "sub" => didi_id,
      "sid" => session_id,
      "iat" => now,
      "exp" => now + ttl,
      "iss" => config(:issuer, "https://id.didi.sh")
    }

    {_meta, compact} =
      Keys.signing_jwk()
      |> JOSE.JWT.sign(%{"alg" => "EdDSA", "kid" => Keys.kid()}, claims)
      |> JOSE.JWS.compact()

    compact
  end

  @doc """
  Verify a compact token: signature (EdDSA only), expiry, issuer.
  Returns `{:ok, %{didi_id: _, session_id: _, exp: _}}` or `{:error, reason}`.
  """
  def verify(token) when is_binary(token) do
    public = JOSE.JWK.to_public(Keys.signing_jwk())

    case JOSE.JWT.verify_strict(public, ["EdDSA"], token) do
      {true, %JOSE.JWT{fields: fields}, _jws} ->
        check_claims(fields)

      {false, _, _} ->
        {:error, :bad_signature}

      _ ->
        {:error, :malformed}
    end
  rescue
    _ -> {:error, :malformed}
  end

  def verify(_), do: {:error, :missing}

  defp check_claims(%{"sub" => sub, "sid" => sid, "exp" => exp, "iss" => iss}) do
    cond do
      iss != config(:issuer, "https://id.didi.sh") -> {:error, :bad_issuer}
      not is_integer(exp) -> {:error, :malformed}
      exp <= System.system_time(:second) -> {:error, :expired}
      true -> {:ok, %{didi_id: sub, session_id: sid, exp: exp}}
    end
  end

  defp check_claims(_), do: {:error, :malformed}

  defp config(key, default) do
    Application.get_env(:id_didi_sh, :identity, [])
    |> Keyword.get(key, default)
  end
end
