defmodule IdDidiShWeb.ResolveController do
  @moduledoc """
  The one endpoint that returns a credential's plaintext.

  Reachable only by a registered server-side app (see
  `IdDidiShWeb.Plugs.RequireApp`), never by a person's browser. Every successful
  call writes a `credential_usage` row, because a lender who cannot see what
  their card paid for has no basis to leave a key lent.
  """

  use IdDidiShWeb, :controller

  alias IdDidiSh.Credentials

  def create(conn, %{"entity_id" => entity_id, "provider" => provider} = params) do
    app = conn.assigns.current_app

    opts = [
      didi_id: params["didi_id"],
      units: params["units"],
      cost_estimate: params["cost_estimate"]
    ]

    case Credentials.resolve(entity_id, provider, app.slug, opts) do
      {:ok, value} ->
        json(conn, %{value: value})

      {:error, :no_live_loan} ->
        conn
        |> put_status(:not_found)
        |> json(%{
          error: "no_live_loan",
          # Say what a human should do about it, since the caller is a program
          # relaying this to somebody.
          detail: "No live #{provider} credential is lent to this entity. Ask someone to lend one."
        })

      {:error, :cap_exceeded} ->
        conn
        |> put_status(:payment_required)
        |> json(%{
          error: "cap_exceeded",
          detail: "The lender's spend cap for this credential has been reached."
        })
    end
  end

  def create(conn, _params) do
    conn |> put_status(:unprocessable_entity) |> json(%{error: "entity_id_and_provider_required"})
  end
end
