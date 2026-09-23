defmodule IdDidiShWeb.AuthController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts

  @moduledoc """
  The hosted sign-in page — `GET /auth`.

  **This is a deliberate softening of the headless posture.** `AccessController`
  says real sign-in UIs live in the apps, and that stays true: an app that has
  its own login screen should keep calling `POST /api/magic-links` and never send
  anyone here. But didi.sh and the splash both advertise "one login" with no way
  to perform one, and a marketing site whose call-to-action has no destination is
  worse than one with no call-to-action.

  So this is the front door for the case with no app context: somebody arriving
  from didi.sh who wants in. It issues the same magic link the API issues and
  hands off to `/access`, which already does the redemption. Nothing new is
  minted, no second code path exists.

  **Never reveals whether an account exists.** Same invite-only posture as the
  API: every submission renders the same "check your email" page whether or not
  the address is known, because a different answer is an enumeration oracle.
  """

  def new(conn, _params) do
    render(conn, :new, email: nil, error: nil)
  end

  def create(conn, %{"email" => email}) when is_binary(email) do
    trimmed = String.trim(email)

    if trimmed == "" or not String.contains?(trimmed, "@") do
      render(conn, :new, email: trimmed, error: "That does not look like an email address.")
    else
      # Fire and forget, deliberately: the page below says the same thing
      # whatever this returns.
      case Accounts.issue_magic_link(trimmed, app_slug: "didi-sh") do
        {:ok, raw, _token} ->
          Accounts.record_event("magic_link_issued", %{app_slug: "didi-sh"})
          deliver(trimmed, raw)

        {:ok, :noop} ->
          :ok
      end

      render(conn, :sent, email: trimmed)
    end
  end

  def create(conn, _params) do
    render(conn, :new, email: nil, error: "Enter the email you were invited with.")
  end

  defp deliver(email, raw_token) do
    IdDidiSh.Accounts.MagicLinkNotifier.deliver(email, raw_token)
  rescue
    # Same rule as the API path: delivery must never break the flow, and the
    # page has already promised nothing it cannot keep.
    _ -> :ok
  end
end
