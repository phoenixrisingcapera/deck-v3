defmodule IdDidiShWeb.AccountController do
  use IdDidiShWeb, :controller

  alias IdDidiSh.{Accounts, Entities, Token}
  alias IdDidiSh.Entities.Entity
  alias IdDidiSh.Accounts.Membership
  alias IdDidiShWeb.SessionCookie

  @moduledoc """
  `GET /account` — what the credential resolves to, and the controls to change it.

  The first version was read-only and read the WRONG TABLE: it listed
  `Accounts.memberships_for/1`, which is the legacy org-wide `memberships`, while
  the tenancy primitive is `entities` + `entity_memberships`. Both exist — see
  `context-v/issues/Entities-and-Organizations-Both-Exist.md` — so this page now
  shows entities as the answer and orgs as a separate, labelled legacy block
  rather than silently picking one and looking complete.

  Every write here goes through the same context functions the JSON API uses
  (`Entities.create_entity/1`, `Entities.add_member/4`, `Accounts.add_email_alias/2`).
  This is a second *surface*, never a second implementation — the browser and the
  API cannot drift because there is only one place the rule lives.

  **Adding a member takes an email, not a `didi_id`.** Nobody knows their own
  UUID and nobody should have to. A known address is added directly; an unknown
  one gets an invite, because refusing would make the common case — granting
  access to somebody who has never signed in — the case that does not work.
  """

  # ── read ──────────────────────────────────────────────────────────────────

  def show(conn, _params) do
    with_user(conn, fn conn, user, session ->
      render_account(conn, user, session)
    end)
  end

  # ── writes ────────────────────────────────────────────────────────────────

  def update_profile(conn, params) do
    with_user(conn, fn conn, user, _session ->
      case Accounts.update_profile(user, params) do
        {:ok, _} -> back(conn, "Profile saved.")
        {:error, _} -> back(conn, nil, "Could not save that profile.")
      end
    end)
  end

  def add_alias(conn, %{"email" => email}) do
    with_user(conn, fn conn, user, _session ->
      case Accounts.add_email_alias(user, email) do
        {:ok, _} -> back(conn, "#{email} linked to your account.")
        {:error, :invalid_email} -> back(conn, nil, "That does not look like an email address.")
        {:error, reason} -> back(conn, nil, "Could not link that address (#{inspect(reason)}).")
      end
    end)
  end

  def add_entity(conn, params) do
    with_user(conn, fn conn, user, _session ->
      attrs = %{
        "kind" => params["kind"],
        "slug" => String.trim(params["slug"] || ""),
        "name" => String.trim(params["name"] || "")
      }

      case Entities.create_entity(attrs) do
        {:ok, entity} ->
          # The creator is an admin of what they created. Without this the
          # entity exists and nobody — including its author — can administer it.
          Entities.add_member(entity.id, user.didi_id, "org_admin",
            via: "seed",
            granted_by: user.didi_id
          )

          back(conn, "#{entity.name} created — you are its admin.")

        {:error, :slug_taken} ->
          back(conn, nil, "That handle is already taken.")

        {:error, reason} ->
          back(conn, nil, "Could not create that entity (#{inspect(reason)}).")
      end
    end)
  end

  def add_member(conn, %{"entity_id" => entity_id} = params) do
    with_user(conn, fn conn, user, _session ->
      email = String.downcase(String.trim(params["email"] || ""))
      role = params["role"] || "viewer"

      cond do
        Entities.effective_role(entity_id, user.didi_id) not in [
          "org_owner",
          "org_admin",
          "superuser"
        ] ->
          back(conn, nil, "You need admin on that entity to add anyone to it.")

        email == "" ->
          back(conn, nil, "Enter an email address.")

        true ->
          case Accounts.get_user_by_email(email) do
            nil ->
              # Unknown address: invite rather than refuse. Granting access to
              # somebody who has not signed in yet is the COMMON case.
              {:ok, raw, _tok} =
                Accounts.issue_invite(email,
                  entity_id: entity_id,
                  role: role,
                  issued_by: user.didi_id
                )

              # `issue_invite` mints but does not send — the caller chooses the
              # channel. Delivery failing must not roll back a grant that was
              # already recorded, so it is best-effort and the flash says
              # "invited" either way.
              deliver_invite(email, raw)
              back(conn, "Invited #{email} as #{role}.")

            member ->
              case Entities.add_member(entity_id, member.didi_id, role,
                     via: "invite",
                     granted_by: user.didi_id
                   ) do
                {:ok, _} -> back(conn, "#{email} added as #{role}.")
                {:error, reason} -> back(conn, nil, "Could not add them (#{inspect(reason)}).")
              end
          end
      end
    end)
  end

  # ── plumbing ──────────────────────────────────────────────────────────────

  # Auth is checked here rather than by `Plugs.RequireUser`, which halts with a
  # JSON 401 — right for the API scope it was written for, wrong for a browser
  # page, where the answer to "not signed in" is the sign-in page.
  defp with_user(conn, fun) do
    with token when is_binary(token) <- SessionCookie.read(conn),
         {:ok, claims} <- Token.verify(token),
         session when not is_nil(session) <- Accounts.get_live_session(claims.session_id),
         user when not is_nil(user) <- Accounts.get_user(claims.didi_id) do
      fun.(conn, user, session)
    else
      _ -> redirect(conn, to: ~p"/auth")
    end
  end

  defp deliver_invite(email, raw) do
    IdDidiSh.Accounts.InviteNotifier.deliver(email, raw)
  rescue
    _ -> :ok
  end

  defp back(conn, notice, error \\ nil) do
    conn
    |> then(fn c -> if notice, do: put_flash(c, :info, notice), else: c end)
    |> then(fn c -> if error, do: put_flash(c, :error, error), else: c end)
    |> redirect(to: ~p"/account")
  end

  defp render_account(conn, user, session) do
    render(conn, :show,
      user: user,
      session: session,
      alt_emails: Accounts.list_email_aliases(user.didi_id),
      entities: entities_for(user.didi_id),
      legacy_orgs: legacy_orgs_for(user.didi_id),
      kinds: Entity.kinds(),
      roles: Membership.roles(),
      token_verified: true,
      jwks_url: "#{conn.scheme}://#{conn.host}/.well-known/jwks.json"
    )
  end

  # The tenancy primitive. A membership row whose entity is missing still
  # renders its id — an id with no name is a real state, and hiding it would
  # make a broken membership look like no membership.
  defp entities_for(didi_id) do
    didi_id
    |> Entities.memberships_for()
    |> Enum.map(fn m ->
      e = Entities.get_entity(m.entity_id)

      %{
        id: m.entity_id,
        role: m.role,
        via: m.via,
        name: e && e.name,
        slug: e && e.slug,
        kind: e && e.kind,
        admin?: m.role in ["org_owner", "org_admin", "superuser"]
      }
    end)
  end

  # Shown separately and labelled, because both tables exist and picking one
  # silently is how a reader concludes the other is empty.
  defp legacy_orgs_for(didi_id) do
    didi_id
    |> Accounts.memberships_for()
    |> Enum.map(fn m ->
      org = Accounts.get_org(m.org_id)
      %{id: m.org_id, role: m.role, name: org && org.name, slug: org && org.slug}
    end)
  end
end
