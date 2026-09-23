defmodule IdDidiShWeb.Plugs.PutDidiToken do
  @moduledoc """
  Copies the `didi_session` **cookie** into the Plug **session** so a LiveView
  can see it.

  LiveView's `mount/3` receives the Plug session, not the request's cookies, and
  our identity lives in a cookie scoped to `.didi.sh`. Without this bridge a
  LiveView cannot tell who is connected. The token is already a signed JWT, so
  putting it in the session adds no new trust — it is the same value, carried
  somewhere the socket can read.
  """

  import Plug.Conn

  alias IdDidiShWeb.SessionCookie

  def init(opts), do: opts

  def call(conn, _opts) do
    case SessionCookie.read(conn) do
      token when is_binary(token) -> put_session(conn, "didi_token", token)
      _ -> conn
    end
  end
end
