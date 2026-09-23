defmodule IdDidiShWeb.MeController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiShWeb.SessionCookie

  @doc """
  GET /api/me — identity + org memberships for the presented cookie.

  This endpoint is the service itself, so it checks the session ROW as
  well as the token (consumers verifying locally check only the token —
  that asymmetry is the design: revocation is strongest at the source).
  """
  def show(conn, _params) do
    with token when is_binary(token) <- SessionCookie.read(conn),
         {:ok, claims} <- Token.verify(token),
         session when not is_nil(session) <- Accounts.get_live_session(claims.session_id),
         user when not is_nil(user) <- Accounts.get_user(claims.didi_id) do
      memberships =
        user.didi_id
        |> Accounts.memberships_for()
        |> Enum.map(&%{org_id: &1.org_id, role: &1.role})

      json(conn, %{
        didi_id: user.didi_id,
        email: user.primary_email,
        alt_emails: Accounts.list_email_aliases(user.didi_id),
        name: user.name,
        handle: user.handle,
        avatar_url: user.avatar_url,
        memberships: memberships,
        session: %{id: session.id, expires_at: session.expires_at}
      })
    else
      _ -> conn |> put_status(401) |> json(%{error: "unauthenticated"})
    end
  end
end
