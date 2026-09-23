defmodule IdDidiShWeb.Plugs.RequireApp do
  @moduledoc """
  Authenticates a **registered server-side app** by bearer token and assigns
  `:current_app`.

  Deliberately refuses a user session even if one is present. The endpoint
  behind this hands back a credential's plaintext, and Ruling 3's invariant is
  that a human borrower never sees a value. If a browser could reach it by
  carrying a cookie, the invariant would be broken by the transport rather than
  by anyone's intent — so the cookie is not merely ignored, it is rejected with
  a message saying why.
  """

  import Plug.Conn

  alias IdDidiSh.Accounts

  def init(opts), do: opts

  def call(conn, _opts) do
    cond do
      has_session_cookie?(conn) ->
        deny(conn, "app_credential_required", :forbidden)

      true ->
        case bearer(conn) do
          nil ->
            deny(conn, "app_credential_required", :unauthorized)

          raw ->
            case Accounts.authenticate_app(raw) do
              {:ok, app} -> assign(conn, :current_app, app)
              {:error, :app_disabled} -> deny(conn, "app_disabled", :forbidden)
              {:error, _} -> deny(conn, "invalid_app_credential", :unauthorized)
            end
        end
    end
  end

  defp has_session_cookie?(conn) do
    conn = fetch_cookies(conn)
    Map.has_key?(conn.cookies, "didi_session")
  end

  defp bearer(conn) do
    case get_req_header(conn, "authorization") do
      ["Bearer " <> token | _] -> String.trim(token)
      _ -> nil
    end
  end

  defp deny(conn, error, status) do
    conn
    |> put_status(status)
    |> Phoenix.Controller.json(%{error: error})
    |> halt()
  end
end
