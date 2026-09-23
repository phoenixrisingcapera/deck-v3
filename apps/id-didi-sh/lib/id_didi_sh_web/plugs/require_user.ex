defmodule IdDidiShWeb.Plugs.RequireUser do
  @moduledoc """
  Authenticates the `didi_session` cookie and assigns `:current_user`.

  Same three-step check `MeController` does inline: verify the token
  signature, confirm the session ROW is still live (revocation is strongest
  at the source), then load the user. Extracted because every entity endpoint
  needs it and copy-pasting a `with` chain per action is how one of them
  quietly ends up missing the session-row check.

  Halts with 401 and `{"error": "unauthenticated"}` on any failure — the same
  shape `/api/me` already returns.
  """

  import Plug.Conn

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiShWeb.SessionCookie

  def init(opts), do: opts

  def call(conn, _opts) do
    with token when is_binary(token) <- SessionCookie.read(conn),
         {:ok, claims} <- Token.verify(token),
         session when not is_nil(session) <- Accounts.get_live_session(claims.session_id),
         user when not is_nil(user) <- Accounts.get_user(claims.didi_id) do
      conn
      |> assign(:current_user, user)
      |> assign(:current_session, session)
    else
      _ ->
        conn
        |> put_status(:unauthorized)
        |> Phoenix.Controller.json(%{error: "unauthenticated"})
        |> halt()
    end
  end
end
