defmodule IdDidiShWeb.AccessController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiShWeb.SessionCookie

  @moduledoc """
  The hosted magic-link landing — the minimal fallback page the emails
  point at (`/access?token=…`). Deliberately two-step: the GET renders a
  confirm button and does NOT touch the token, so mail-scanner prefetch
  can't consume a single-use link; only the explicit POST redeems.

  This page stays minimal on purpose (the GTM headless contract: real
  sign-in UIs live in the apps). It exists for the click-from-email path
  and edge cases with no app context.
  """

  def show(conn, params) do
    render(conn, :show, token: params["token"], error: nil)
  end

  def redeem(conn, %{"token" => raw}) do
    # One landing page, two token kinds. A magic link signs an existing person
    # back in; an invite creates the account and attaches whatever membership it
    # was issued for. The person clicking cannot tell which they have, so the
    # page must not care either — try the invite path when the magic-link path
    # rejects the token.
    case redeem_any(raw) do
      {:ok, user, login_token} ->
        session =
          Accounts.create_session(user, %{
            user_agent: conn |> get_req_header("user-agent") |> List.first()
          })

        Accounts.record_event("sign_in", %{
          didi_id: user.didi_id,
          app_slug: login_token.app_slug,
          payload: %{"method" => "magic_link", "surface" => "access_page"}
        })

        jwt = Token.sign(user.didi_id, session.id)
        conn = SessionCookie.put(conn, jwt)

        case safe_next(login_token.next_path) do
          nil -> render(conn, :done, email: user.primary_email)
          next -> redirect(conn, external: next)
        end

      {:error, :invalid_token} ->
        render(conn, :show,
          token: nil,
          error:
            "That link is invalid or expired — they're single-use and short-lived. Request a fresh one from the app you were signing into."
        )
    end
  end

  def redeem(conn, _params), do: redirect(conn, to: ~p"/access")

  # Magic link first (the common case), then invite. Both enforce single-use
  # and TTL atomically in their own claim query, so trying one then the other
  # cannot double-claim.
  defp redeem_any(raw) do
    case Accounts.redeem_magic_link(raw) do
      {:ok, user, token} ->
        {:ok, user, token}

      {:error, :invalid_token} ->
        case Accounts.redeem_invite(raw) do
          {:ok, user, token} ->
            attach_invited_membership(user, token)
            {:ok, user, token}

          error ->
            error
        end
    end
  end

  # The invite carried a destination. Attach it now that the account exists.
  # Failure here must not strand the person outside the thing they were invited
  # to without a trace, so it is recorded either way.
  defp attach_invited_membership(user, %{entity_id: entity_id, role: role})
       when is_binary(entity_id) and is_binary(role) do
    case IdDidiSh.Entities.add_member(entity_id, user.didi_id, role, via: "invite") do
      {:ok, _} ->
        Accounts.record_event("invite_membership_attached", %{
          didi_id: user.didi_id,
          payload: %{"entity_id" => entity_id, "role" => role}
        })

      {:error, reason} ->
        Accounts.record_event("invite_membership_failed", %{
          didi_id: user.didi_id,
          payload: %{"entity_id" => entity_id, "role" => role, "reason" => inspect(reason)}
        })
    end
  end

  defp attach_invited_membership(_user, _token), do: :ok

  # Only same-site relative paths or *.didi.sh URLs — never an open redirect.
  defp safe_next(nil), do: nil
  defp safe_next("/" <> _ = path), do: path

  defp safe_next(url) when is_binary(url) do
    case URI.parse(url) do
      %URI{scheme: "https", host: host} when is_binary(host) ->
        if host == "didi.sh" or String.ends_with?(host, ".didi.sh"), do: url, else: nil

      _ ->
        nil
    end
  end
end
