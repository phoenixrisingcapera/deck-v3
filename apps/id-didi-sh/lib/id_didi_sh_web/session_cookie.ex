defmodule IdDidiShWeb.SessionCookie do
  @moduledoc """
  The `didi_session` cookie: HttpOnly, Secure (prod), SameSite=Lax, and —
  deployed — `Domain=.didi.sh` so every service subdomain receives it.
  Dev/test use a host-only cookie (no domain) on localhost.

  The cookie's max_age tracks the SERVER session TTL (30d rolling); the
  signed token inside expires much sooner (~12h) and is re-minted by
  /api/session/refresh. Verification always checks the token's own exp.
  """

  import Plug.Conn

  def cookie_name, do: config(:cookie_name, "didi_session")

  def put(conn, token) do
    put_resp_cookie(conn, cookie_name(), token, cookie_opts())
  end

  def clear(conn) do
    delete_resp_cookie(conn, cookie_name(), cookie_opts())
  end

  def read(conn) do
    conn = fetch_cookies(conn)
    conn.cookies[cookie_name()]
  end

  defp cookie_opts do
    ttl_days = config(:session_ttl_days, 30)

    base = [
      http_only: true,
      same_site: "Lax",
      secure: config(:cookie_secure, false),
      max_age: ttl_days * 24 * 60 * 60,
      path: "/"
    ]

    case config(:cookie_domain, nil) do
      nil -> base
      domain -> Keyword.put(base, :domain, domain)
    end
  end

  defp config(key, default) do
    Application.get_env(:id_didi_sh, :identity, []) |> Keyword.get(key, default)
  end
end
