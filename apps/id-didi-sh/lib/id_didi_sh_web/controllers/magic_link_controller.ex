defmodule IdDidiShWeb.MagicLinkController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiShWeb.SessionCookie

  @doc """
  POST /api/magic-links  { email, app?, next? }

  Always 202 — the response never reveals whether the email has an account
  (invite-only posture; no enumeration). In dev, `echo_login_tokens: true`
  returns the raw token in the response so the prove-skeleton script can
  run without reading the mailbox.
  """
  def create(conn, %{"email" => email} = params) do
    result =
      Accounts.issue_magic_link(email,
        app_slug: params["app"],
        next_path: params["next"]
      )

    case result do
      {:ok, raw, _token} ->
        Accounts.record_event("magic_link_issued", %{app_slug: params["app"]})
        deliver_email(email, raw)

        body = %{status: "accepted"}
        body = if echo_tokens?(), do: Map.put(body, :dev_token, raw), else: body
        conn |> put_status(202) |> json(body)

      {:ok, :noop} ->
        conn |> put_status(202) |> json(%{status: "accepted"})
    end
  end

  def create(conn, _params) do
    conn |> put_status(400) |> json(%{error: "email is required"})
  end

  @doc """
  POST /api/magic-links/redeem  { token }

  Single-use + TTL enforced in Accounts. On success: session row created,
  EdDSA token minted, cookie set. Returns identity + the `next` path the
  issuing app asked to land on.
  """
  def redeem(conn, %{"token" => raw}) do
    case Accounts.redeem_magic_link(raw) do
      {:ok, user, login_token} ->
        session =
          Accounts.create_session(user, %{
            user_agent: first_header(conn, "user-agent"),
            ip: remote_ip(conn)
          })

        Accounts.record_event("sign_in", %{
          didi_id: user.didi_id,
          app_slug: login_token.app_slug,
          payload: %{"method" => "magic_link"}
        })

        jwt = Token.sign(user.didi_id, session.id)

        conn
        |> SessionCookie.put(jwt)
        |> json(%{
          didi_id: user.didi_id,
          email: user.primary_email,
          next: login_token.next_path
        })

      {:error, :invalid_token} ->
        conn |> put_status(401) |> json(%{error: "invalid or expired token"})
    end
  end

  def redeem(conn, _params) do
    conn |> put_status(400) |> json(%{error: "token is required"})
  end

  defp deliver_email(email, raw_token) do
    IdDidiSh.Accounts.MagicLinkNotifier.deliver(email, raw_token)
  rescue
    # Email delivery must never break the flow in the skeleton; the dev
    # echo (and later, provider retries) cover it.
    _ -> :ok
  end

  defp echo_tokens? do
    Application.get_env(:id_didi_sh, :identity, [])
    |> Keyword.get(:echo_login_tokens, false)
  end

  defp first_header(conn, name) do
    conn |> get_req_header(name) |> List.first()
  end

  defp remote_ip(conn) do
    conn.remote_ip |> :inet.ntoa() |> to_string()
  rescue
    _ -> nil
  end
end
