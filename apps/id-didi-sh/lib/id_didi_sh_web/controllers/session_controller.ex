defmodule IdDidiShWeb.SessionController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiShWeb.SessionCookie

  @doc """
  POST /api/session/refresh

  The silent-refresh path: accepts the current cookie even if its token
  just expired (the SESSION row is the authority for refresh), re-mints,
  and rolls the session forward. Apps call this same-site with
  credentials when they see exp approaching.
  """
  def refresh(conn, _params) do
    with token when is_binary(token) <- SessionCookie.read(conn),
         {:ok, claims} <- verify_allowing_expired(token),
         session when not is_nil(session) <- Accounts.get_live_session(claims.session_id) do
      session = Accounts.touch_session(session)
      jwt = Token.sign(session.didi_id, session.id)

      conn
      |> SessionCookie.put(jwt)
      |> json(%{status: "refreshed", didi_id: session.didi_id})
    else
      _ ->
        conn
        |> SessionCookie.clear()
        |> put_status(401)
        |> json(%{error: "no live session"})
    end
  end

  @doc "DELETE /api/session — logout everywhere: kill the row, clear the cookie domain-wide."
  def delete(conn, _params) do
    with token when is_binary(token) <- SessionCookie.read(conn),
         {:ok, claims} <- verify_allowing_expired(token) do
      Accounts.revoke_session(claims.session_id)
      Accounts.record_event("sign_out", %{didi_id: claims.didi_id})
    end

    conn
    |> SessionCookie.clear()
    |> json(%{status: "signed_out"})
  end

  # Refresh/logout accept an expired-but-authentic token: the signature
  # still proves possession, and the session row decides liveness.
  defp verify_allowing_expired(token) do
    case Token.verify(token) do
      {:ok, claims} -> {:ok, claims}
      {:error, :expired} -> decode_unverified_sid(token)
      error -> error
    end
  end

  defp decode_unverified_sid(token) do
    # Signature already validated inside Token.verify before the exp check
    # failed, so re-verify signature-only here via peek + strict verify of
    # signature: JOSE verify_strict validated sig before claims; expired
    # comes from our own claim check. Safe to peek.
    case JOSE.JWT.peek_payload(token) do
      %JOSE.JWT{fields: %{"sub" => sub, "sid" => sid}} ->
        public = JOSE.JWK.to_public(IdDidiSh.Keys.signing_jwk())

        case JOSE.JWT.verify_strict(public, ["EdDSA"], token) do
          {true, _, _} -> {:ok, %{didi_id: sub, session_id: sid, exp: nil}}
          _ -> {:error, :bad_signature}
        end

      _ ->
        {:error, :malformed}
    end
  rescue
    _ -> {:error, :malformed}
  end
end
