defmodule IdDidiShWeb.CredentialController do
  @moduledoc """
  The lender's surface: paste a key, lend it, watch it, take it back.

  Ruling 4 is the reason this exists. The reason people hesitate to share a key
  is not missing permissions — it is that once shared they are blind and
  brakeless, and their only lever is the nuclear one. So a lender gets a meter
  (`usage`) and a stop-button (`DELETE` on a cascade or a single loan).

  Every response here goes through `Credentials.render/1`, which is built by
  naming safe fields rather than dropping unsafe ones. No action in this module
  can emit a credential's value.
  """

  use IdDidiShWeb, :controller

  alias IdDidiSh.Credentials

  ## Credentials

  def index(conn, _params) do
    creds =
      conn.assigns.current_user.didi_id
      |> Credentials.list_credentials()
      |> Enum.map(&Credentials.render/1)

    json(conn, %{credentials: creds})
  end

  def create(conn, params) do
    user = conn.assigns.current_user

    case Credentials.create_credential(
           user.didi_id,
           params["provider"],
           params["label"],
           params["value"] || ""
         ) do
      {:ok, credential} ->
        conn |> put_status(:created) |> json(%{credential: Credentials.render(credential)})

      {:error, reason} ->
        error(conn, :unprocessable_entity, reason)
    end
  end

  def delete(conn, %{"id" => id}) do
    case Credentials.revoke_credential(id, conn.assigns.current_user.didi_id) do
      {:ok, credential} -> json(conn, %{credential: Credentials.render(credential)})
      {:error, :not_found} -> error(conn, :not_found, :not_found)
      {:error, :not_the_owner} -> error(conn, :forbidden, :not_the_owner)
    end
  end

  ## Lending

  @doc """
  POST /api/credentials/:credential_id/cascades

  One act, N entities. `entity_ids` is a list because that is the gesture:
  "this organization, that workspace, that project."
  """
  def lend(conn, %{"credential_id" => credential_id} = params) do
    user = conn.assigns.current_user
    entity_ids = List.wrap(params["entity_ids"])

    terms =
      %{}
      |> maybe_put(:spend_cap, params["spend_cap"])
      |> maybe_put(:cap_period, params["cap_period"])
      |> maybe_put_dt(:expires_at, params["expires_at"])

    case Credentials.lend(credential_id, entity_ids, terms, user.didi_id) do
      {:ok, cascade, loans} ->
        conn
        |> put_status(:created)
        |> json(%{
          cascade: render_cascade(cascade),
          loans: Enum.map(loans, &%{entity_id: &1.entity_id}),
          # Say the consequence out loud. A loan follows the entity, so it
          # reaches whoever joins later — a lender who learns that after the
          # fact never lends again.
          notice:
            "This lends to everyone in #{length(loans)} " <>
              ngettext_entity(length(loans)) <> ", including anyone added later."
        })

      {:error, reason} ->
        error(conn, :unprocessable_entity, reason)
    end
  end

  @doc "DELETE /api/cascades/:id — take the key back from everywhere at once."
  def end_cascade(conn, %{"id" => id}) do
    case Credentials.end_cascade(id, conn.assigns.current_user.didi_id) do
      {:ok, cascade} -> json(conn, %{cascade: render_cascade(cascade)})
      {:error, :not_found} -> error(conn, :not_found, :not_found)
      {:error, :not_the_lender} -> error(conn, :forbidden, :not_the_lender)
    end
  end

  @doc """
  DELETE /api/cascades/:id/loans/:entity_id — partial withdrawal.

  For when one collaboration sours and the others do not.
  """
  def end_loan(conn, %{"id" => id, "entity_id" => entity_id}) do
    case Credentials.end_loan(id, entity_id, conn.assigns.current_user.didi_id) do
      :ok -> json(conn, %{ended: %{cascade_id: id, entity_id: entity_id}})
      {:error, :not_found} -> error(conn, :not_found, :not_found)
      {:error, :not_the_lender} -> error(conn, :forbidden, :not_the_lender)
      {:error, :no_live_loan} -> error(conn, :not_found, :no_live_loan)
    end
  end

  ## The meter

  @doc """
  GET /api/credentials/:credential_id/usage

  **Owner only** (plan OQ 4, decided here). The meter answers "what is my card
  paying for, and for whom" — it is the lender's evidence about their own
  spending, and exposing per-caller detail to an entity admin would tell them
  who used what without those people having agreed to that. An aggregate view
  for entity admins can be added later if someone actually wants it; the
  narrower default is the recoverable one.
  """
  def usage(conn, %{"credential_id" => credential_id}) do
    user = conn.assigns.current_user

    case Credentials.get_credential(credential_id) do
      nil ->
        error(conn, :not_found, :not_found)

      %{owner_didi_id: owner} when owner != user.didi_id ->
        error(conn, :forbidden, :not_the_owner)

      credential ->
        json(conn, %{
          credential: Credentials.render(credential),
          by_entity: Credentials.usage_for_credential(credential_id)
        })
    end
  end

  ## Helpers

  defp render_cascade(c) do
    %{
      id: c.id,
      credential_id: c.credential_id,
      lent_by: c.lent_by,
      lent_at: c.lent_at,
      spend_cap: c.spend_cap,
      cap_period: c.cap_period,
      expires_at: c.expires_at,
      ended_at: c.ended_at
    }
  end

  defp ngettext_entity(1), do: "entity"
  defp ngettext_entity(_), do: "entities"

  defp maybe_put(map, _key, nil), do: map
  defp maybe_put(map, key, value), do: Map.put(map, key, value)

  defp maybe_put_dt(map, _key, nil), do: map

  defp maybe_put_dt(map, key, value) do
    case DateTime.from_iso8601(to_string(value)) do
      {:ok, dt, _} -> Map.put(map, key, DateTime.truncate(dt, :second))
      _ -> map
    end
  end

  defp error(conn, status, reason) do
    conn |> put_status(status) |> json(%{error: to_string(reason)})
  end
end
