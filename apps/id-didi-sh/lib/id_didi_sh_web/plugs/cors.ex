defmodule IdDidiShWeb.Plugs.CORS do
  @moduledoc """
  Config-driven CORS for the headless API — the seam that lets each
  service's own signup/login UI call id.didi.sh from the browser (the
  GTM headless contract).

  Allowed origins come from `config :id_didi_sh, :identity, cors_origins:`.
  Dev lists the local shells (`http://localhost:3100`, …); production
  lists the `https://*.didi.sh` service origins explicitly (enumerate,
  don't wildcard — the allowlist IS the trust boundary statement).

  Credentials are always allowed for matched origins (the whole point is
  the didi_session cookie), which is why the origin echo is exact-match
  against the allowlist, never `*`.
  """

  import Plug.Conn

  def init(opts), do: opts

  def call(conn, _opts) do
    origin = conn |> get_req_header("origin") |> List.first()

    cond do
      is_nil(origin) or origin not in allowed_origins() ->
        conn

      conn.method == "OPTIONS" ->
        conn
        |> put_cors_headers(origin)
        |> put_resp_header("access-control-allow-methods", "GET, POST, DELETE, OPTIONS")
        |> put_resp_header("access-control-allow-headers", "content-type")
        |> put_resp_header("access-control-max-age", "600")
        |> send_resp(204, "")
        |> halt()

      true ->
        put_cors_headers(conn, origin)
    end
  end

  defp put_cors_headers(conn, origin) do
    conn
    |> put_resp_header("access-control-allow-origin", origin)
    |> put_resp_header("access-control-allow-credentials", "true")
    |> put_resp_header("vary", "origin")
  end

  defp allowed_origins do
    Application.get_env(:id_didi_sh, :identity, [])
    |> Keyword.get(:cors_origins, [])
  end
end
