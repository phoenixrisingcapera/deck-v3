defmodule IdDidiShWeb.EntityController do
  @moduledoc """
  Entities and their memberships.

  The endpoint worth reading twice is `delete_member/2`. It returns
  `also_member_of` — every OTHER entity the removed person still belongs to —
  because entities are flat and removal never cascades (Ruling 1b). Whoever
  clicks "remove" otherwise believes they have offboarded someone who is still
  in three other places. Enforcing the disclosure *at the API* means any client,
  including one nobody has written yet, gets it right.
  """

  use IdDidiShWeb, :controller

  alias IdDidiSh.Accounts
  alias IdDidiSh.Entities
  alias IdDidiSh.Accounts.InviteNotifier

  # Roles that may administer an entity. Shared lattice with org-wide
  # memberships; see plan OQ 2 on whether projects eventually need their own.
  @admin_roles ~w(superuser org_owner org_admin)

  ## Entities

  def index(conn, _params) do
    user = conn.assigns.current_user
    json(conn, %{entities: Enum.map(Entities.list_entities_for(user.didi_id), &render_entity/1)})
  end

  def create(conn, params) do
    user = conn.assigns.current_user

    case Entities.create_entity(%{
           kind: params["kind"],
           slug: params["slug"],
           name: params["name"],
           org_id: params["org_id"]
         }) do
      {:ok, entity} ->
        # The creator is an owner of what they created. Without this an entity
        # is born with nobody able to administer it.
        {:ok, _} =
          Entities.add_member(entity.id, user.didi_id, "org_owner",
            via: "seed",
            granted_by: user.didi_id
          )

        conn |> put_status(:created) |> json(%{entity: render_entity(entity)})

      {:error, reason} ->
        error(conn, :unprocessable_entity, reason)
    end
  end

  def show(conn, %{"id" => id}) do
    user = conn.assigns.current_user

    case Entities.get_entity(id) do
      nil ->
        error(conn, :not_found, :unknown_entity)

      entity ->
        case Entities.effective_role(entity.id, user.didi_id) do
          nil ->
            error(conn, :forbidden, :not_a_member)

          role ->
            json(conn, %{entity: render_entity(entity), effective_role: role})
        end
    end
  end

  ## Members

  def list_members(conn, %{"entity_id" => entity_id}) do
    with {:ok, _entity} <- fetch_entity(entity_id),
         :ok <- require_member(conn, entity_id) do
      json(conn, %{members: Enum.map(Entities.list_members(entity_id), &render_member/1)})
    else
      {:error, status, reason} -> error(conn, status, reason)
    end
  end

  @doc """
  POST /api/entities/:entity_id/members

  Two outcomes by design, and the caller is told which:

  - the email already has a didi account -> membership attached immediately,
    `201 {"member": ...}`
  - it does not -> an invite is emailed from `no-reply@didi.sh`, and the
    membership is attached when they redeem it, `202 {"invited": ...}`

  The 202 matters. Adding someone who has never heard of didi.sh is not a
  failure and should not read like one, but it also has not happened yet — a
  201 would claim a member who cannot sign in.
  """
  def add_member(conn, %{"entity_id" => entity_id} = params) do
    actor = conn.assigns.current_user
    email = String.downcase(String.trim(params["email"] || ""))
    role = params["role"] || "viewer"

    with {:ok, entity} <- fetch_entity(entity_id),
         :ok <- require_admin(conn, entity_id),
         :ok <- validate_role(role) do
      case Accounts.get_user_by_email(email) do
        nil ->
          invite(conn, entity, email, role, actor)

        user ->
          case Entities.add_member(entity_id, user.didi_id, role,
                 via: "invite",
                 granted_by: actor.didi_id
               ) do
            {:ok, m} -> conn |> put_status(:created) |> json(%{member: render_member(m)})
            {:error, reason} -> error(conn, :unprocessable_entity, reason)
          end
      end
    else
      {:error, status, reason} -> error(conn, status, reason)
    end
  end

  defp invite(conn, entity, email, role, actor) do
    {:ok, raw, _token} =
      Accounts.issue_invite(email,
        entity_id: entity.id,
        role: role,
        issued_by: actor.didi_id
      )

    # Delivery failure must not silently swallow the invite — the row exists
    # either way, so the operator can resend rather than wonder.
    delivery =
      case InviteNotifier.deliver(email, raw,
             entity_name: entity.name,
             inviter_name: actor.name || actor.primary_email
           ) do
        {:ok, _} -> "sent"
        {:error, _} -> "queued_delivery_failed"
      end

    conn
    |> put_status(:accepted)
    |> json(%{
      invited: %{email: email, role: role, entity_id: entity.id},
      delivery: delivery
    })
  end

  defp validate_role(role) do
    if role in IdDidiSh.Accounts.Membership.roles(),
      do: :ok,
      else: {:error, :unprocessable_entity, :invalid_role}
  end

  @doc """
  DELETE /api/entities/:entity_id/members/:didi_id

  Removes exactly one membership and reports what survives. See the moduledoc.
  """
  def delete_member(conn, %{"entity_id" => entity_id, "didi_id" => didi_id}) do
    with {:ok, _entity} <- fetch_entity(entity_id),
         :ok <- require_admin(conn, entity_id) do
      # Read the survivors BEFORE removing, so the response describes the world
      # the caller is creating rather than racing it.
      survivors = Entities.also_member_of(didi_id, entity_id)
      :ok = Entities.remove_member(entity_id, didi_id)

      json(conn, %{
        removed: %{entity_id: entity_id, didi_id: didi_id},
        also_member_of: Enum.map(survivors, &render_entity/1),
        disclosure: disclosure_sentence(didi_id, survivors)
      })
    else
      {:error, status, reason} -> error(conn, status, reason)
    end
  end

  ## Helpers

  defp fetch_entity(id) do
    case Entities.get_entity(id) do
      nil -> {:error, :not_found, :unknown_entity}
      entity -> {:ok, entity}
    end
  end

  defp require_member(conn, entity_id) do
    case Entities.effective_role(entity_id, conn.assigns.current_user.didi_id) do
      nil -> {:error, :forbidden, :not_a_member}
      _ -> :ok
    end
  end

  defp require_admin(conn, entity_id) do
    case Entities.effective_role(entity_id, conn.assigns.current_user.didi_id) do
      role when role in @admin_roles -> :ok
      nil -> {:error, :forbidden, :not_a_member}
      _ -> {:error, :forbidden, :not_an_admin}
    end
  end

  # The sentence a UI should show. Built here so every client says the same
  # true thing, rather than each inventing its own phrasing or omitting it.
  defp disclosure_sentence(didi_id, []),
    do: "#{label_for(didi_id)} will no longer have access to anything here."

  defp disclosure_sentence(didi_id, survivors) do
    names = survivors |> Enum.map(& &1.name) |> Enum.join(", ")
    "#{label_for(didi_id)} will keep access to: #{names}."
  end

  defp label_for(didi_id) do
    case Accounts.get_user(didi_id) do
      nil -> didi_id
      user -> user.name || user.primary_email
    end
  end

  defp render_entity(e) do
    %{id: e.id, kind: e.kind, slug: e.slug, name: e.name, org_id: e.org_id}
  end

  defp render_member(m) do
    %{didi_id: m.didi_id, role: m.role, via: m.via, granted_by: m.granted_by}
  end

  defp error(conn, status, reason) do
    conn |> put_status(status) |> json(%{error: to_string(reason)})
  end
end
