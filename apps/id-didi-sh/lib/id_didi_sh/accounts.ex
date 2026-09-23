defmodule IdDidiSh.Accounts do
  @moduledoc """
  The accounts context: users, login tokens (magic links + invites),
  sessions, and auth events.

  Token discipline (mirrors phx.gen.auth / the calmstorm inventory):
  the raw token is random bytes handed to the user exactly once; only its
  SHA-256 hash is stored. Redemption is single-use (`claimed_at`) and
  TTL-bounded. A magic link only ever authenticates an EXISTING user —
  account creation is invite redemption only (not in the walking skeleton).
  """

  import Ecto.Query

  alias IdDidiSh.Repo
  alias IdDidiSh.UUID7
  alias IdDidiSh.Accounts.{User, Membership, LoginToken, Session, UserEmail, Organization, App}

  @rand_bytes 32

  ## Users

  def get_user(didi_id), do: Repo.get(User, didi_id)

  @doc "Resolve a user by primary email OR any alias — one didi_id, many addresses."
  def get_user_by_email(email) when is_binary(email) do
    lower = String.downcase(email)

    Repo.one(from u in User, where: fragment("lower(?)", u.primary_email) == ^lower) ||
      Repo.one(
        from u in User,
          join: e in UserEmail,
          on: e.didi_id == u.didi_id,
          where: fragment("lower(?)", e.email) == ^lower
      )
  end

  @doc """
  Attach an alt email to a user. Rejected when the address is already any
  user's primary or alias (identity addresses are globally unique).
  """
  def add_email_alias(%User{} = user, email) when is_binary(email) do
    lower = String.downcase(String.trim(email))

    cond do
      not Regex.match?(~r/^[^@\s]+@[^@\s]+$/, lower) ->
        {:error, :invalid_email}

      get_user_by_email(lower) != nil ->
        {:error, :taken}

      true ->
        {:ok, _} = Repo.insert(%UserEmail{didi_id: user.didi_id, email: lower})
        {:ok, lower}
    end
  end

  def list_email_aliases(didi_id) do
    Repo.all(from e in UserEmail, where: e.didi_id == ^didi_id, select: e.email)
  end

  @doc """
  Update the profile fields a person owns: display name and handle.

  Email is deliberately not here — an address is added as an alias and verified,
  never edited in place, because editing one would silently move an identity.
  """
  def update_profile(%User{} = user, attrs) do
    user
    |> User.changeset(%{
      name: attrs[:name] || attrs["name"] || user.name,
      handle: attrs[:handle] || attrs["handle"] || user.handle
    })
    |> Repo.update()
  end

  def create_user(attrs) do
    %User{}
    |> User.changeset(Map.put_new(attrs, :didi_id, UUID7.generate()))
    |> Repo.insert()
  end

  def memberships_for(didi_id) do
    Repo.all(from m in Membership, where: m.didi_id == ^didi_id)
  end

  ## Organizations + memberships (seeding path until increment 3's admin)

  @doc "Upsert an organization. `id` is the canonical email domain (domain-as-id)."
  def upsert_org(id, name, slug \\ nil) do
    id = id |> String.trim() |> String.downcase()
    slug = slug || String.replace(id, ".", "-")

    Repo.insert(
      %Organization{id: id, slug: slug, name: name},
      on_conflict: {:replace, [:name, :slug, :updated_at]},
      conflict_target: :id
    )
  end

  def get_org(id), do: Repo.get(Organization, String.downcase(id))

  @doc """
  Upsert a membership (didi_id × org_id → role). Role must be one of
  `Membership.roles/0`; the org must exist. Upsert-by-natural-key: a
  second call with a different role updates the row, never duplicates.
  """
  def upsert_membership(didi_id, org_id, role) do
    org_id = String.downcase(org_id)

    cond do
      role not in Membership.roles() ->
        {:error, :invalid_role}

      is_nil(get_user(didi_id)) ->
        {:error, :unknown_user}

      is_nil(get_org(org_id)) ->
        {:error, :unknown_org}

      true ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        Repo.insert_all(
          Membership,
          [
            %{
              didi_id: didi_id,
              org_id: org_id,
              role: role,
              inserted_at: now,
              updated_at: now
            }
          ],
          on_conflict: {:replace, [:role, :updated_at]},
          conflict_target: [:didi_id, :org_id]
        )

        {:ok, %{didi_id: didi_id, org_id: org_id, role: role}}
    end
  end

  ## Magic links

  @doc """
  Issue a magic-link token for an email. Invite-only posture: if no user
  exists for the email, returns `{:ok, :noop}` — callers respond 202 either
  way so the endpoint doesn't enumerate accounts.

  Returns `{:ok, raw_token, login_token}` when issued.
  """
  def issue_magic_link(email, opts \\ []) do
    case get_user_by_email(email) do
      nil ->
        {:ok, :noop}

      %User{} = user ->
        raw = :crypto.strong_rand_bytes(@rand_bytes) |> Base.url_encode64(padding: false)
        ttl_min = config(:magic_link_ttl_minutes, 15)

        token = %LoginToken{
          kind: "magic_link",
          token_hash: hash(raw),
          email: user.primary_email,
          didi_id: user.didi_id,
          app_slug: Keyword.get(opts, :app_slug),
          next_path: Keyword.get(opts, :next_path),
          expires_at: DateTime.add(now(), ttl_min * 60) |> DateTime.truncate(:second)
        }

        {:ok, token} = Repo.insert(token)
        {:ok, raw, token}
    end
  end

  @doc """
  Issue an INVITE token for an email that may not have an account yet.

  This is the signup path: unlike `issue_magic_link/2`, which refuses unknown
  emails to avoid enumeration, an invite is issued *by* an authenticated person
  who is deliberately naming someone. Redeeming it creates the account.

  `opts`: `:entity_id`, `:role`, `:issued_by`, `:app_slug`, `:next_path`.

  Returns `{:ok, raw_token, login_token}`. The raw token is returned exactly
  once — only its hash is stored.
  """
  def issue_invite(email, opts \\ []) do
    email = String.downcase(String.trim(email))
    raw = :crypto.strong_rand_bytes(@rand_bytes) |> Base.url_encode64(padding: false)
    ttl_days = config(:invite_ttl_days, 7)

    token = %LoginToken{
      kind: "invite",
      token_hash: hash(raw),
      email: email,
      # An invite may precede the account; didi_id is filled in on redemption.
      didi_id: get_user_by_email(email) |> then(&(&1 && &1.didi_id)),
      entity_id: Keyword.get(opts, :entity_id),
      org_id: Keyword.get(opts, :org_id),
      role: Keyword.get(opts, :role),
      issued_by: Keyword.get(opts, :issued_by),
      app_slug: Keyword.get(opts, :app_slug),
      next_path: Keyword.get(opts, :next_path),
      expires_at: DateTime.add(now(), ttl_days * 24 * 60 * 60) |> DateTime.truncate(:second)
    }

    {:ok, token} = Repo.insert(token)
    {:ok, raw, token}
  end

  @doc """
  Redeem an invite: single-use + TTL enforced atomically, exactly as magic
  links are. Creates the user if the email has no account yet — this is the
  only path that creates accounts.

  Returns `{:ok, user, login_token}` or `{:error, :invalid_token}`. Attaching
  the entity membership the invite carried is the caller's job, so this context
  does not depend on Entities.
  """
  def redeem_invite(raw) when is_binary(raw) do
    token_hash = hash(raw)
    now = DateTime.truncate(now(), :second)

    claim =
      from t in LoginToken,
        where:
          t.token_hash == ^token_hash and t.kind == "invite" and
            is_nil(t.claimed_at) and t.expires_at > ^now

    case Repo.update_all(claim, set: [claimed_at: now]) do
      {1, _} ->
        token = Repo.one!(from t in LoginToken, where: t.token_hash == ^token_hash)

        user =
          case get_user_by_email(token.email) do
            nil ->
              {:ok, user} = create_user(%{primary_email: token.email})
              user

            existing ->
              existing
          end

        {:ok, user, token}

      _ ->
        {:error, :invalid_token}
    end
  end

  def redeem_invite(_), do: {:error, :invalid_token}

  @doc """
  Redeem a magic-link token: single-use + TTL enforced atomically (the
  UPDATE claims the row only if unclaimed and unexpired). Returns
  `{:ok, user, login_token}` or `{:error, :invalid_token}`.
  """
  def redeem_magic_link(raw) when is_binary(raw) do
    token_hash = hash(raw)
    now = DateTime.truncate(now(), :second)

    claim =
      from t in LoginToken,
        where:
          t.token_hash == ^token_hash and t.kind == "magic_link" and
            is_nil(t.claimed_at) and t.expires_at > ^now

    case Repo.update_all(claim, set: [claimed_at: now]) do
      {1, _} ->
        token = Repo.one!(from t in LoginToken, where: t.token_hash == ^token_hash)
        user = get_user(token.didi_id)
        {:ok, user, token}

      _ ->
        {:error, :invalid_token}
    end
  end

  def redeem_magic_link(_), do: {:error, :invalid_token}

  ## Apps (server-to-server consumers)

  def get_app(slug) when is_binary(slug), do: Repo.get(App, slug)
  def get_app(_), do: nil

  def upsert_app(slug, name) do
    now = DateTime.truncate(now(), :second)

    Repo.insert(
      %App{slug: slug, name: name, inserted_at: now, updated_at: now},
      on_conflict: {:replace, [:name, :updated_at]},
      conflict_target: [:slug]
    )
  end

  @doc """
  Mint a server-to-server token for a registered app.

  Returned raw exactly once — only the hash is stored, same discipline as magic
  links. Re-issuing replaces the previous token, which is also how you revoke.
  """
  def issue_app_token(slug) do
    case get_app(slug) do
      nil ->
        {:error, :unknown_app}

      app ->
        raw = :crypto.strong_rand_bytes(@rand_bytes) |> Base.url_encode64(padding: false)
        now = DateTime.truncate(now(), :second)

        {:ok, app} =
          app
          |> Ecto.Changeset.change(token_hash: hash(raw), token_issued_at: now, updated_at: now)
          |> Repo.update()

        {:ok, raw, app}
    end
  end

  @doc """
  Authenticate a raw app token. Disabled apps are refused even with a valid
  token — the flag is the off switch.
  """
  def authenticate_app(raw) when is_binary(raw) do
    case Repo.get_by(App, token_hash: hash(raw)) do
      nil -> {:error, :invalid_token}
      %App{enabled: false} -> {:error, :app_disabled}
      app -> {:ok, app}
    end
  end

  def authenticate_app(_), do: {:error, :invalid_token}

  ## Sessions

  @doc "Create a session row for a user. Returns the session."
  def create_session(%User{} = user, attrs \\ %{}) do
    ttl_days = config(:session_ttl_days, 30)
    now = DateTime.truncate(now(), :second)

    Repo.insert!(%Session{
      id: UUID7.generate(),
      didi_id: user.didi_id,
      expires_at: DateTime.add(now, ttl_days * 24 * 60 * 60),
      last_seen_at: now,
      user_agent: attrs[:user_agent],
      ip: attrs[:ip]
    })
  end

  @doc "A session is alive if it exists, is unrevoked, and is unexpired."
  def get_live_session(session_id) when is_binary(session_id) do
    now = DateTime.truncate(now(), :second)

    Repo.one(
      from s in Session,
        where: s.id == ^session_id and is_nil(s.revoked_at) and s.expires_at > ^now
    )
  end

  def get_live_session(_), do: nil

  @doc "Rolling refresh: bump last_seen_at + extend expires_at."
  def touch_session(%Session{} = session) do
    ttl_days = config(:session_ttl_days, 30)
    now = DateTime.truncate(now(), :second)

    session
    |> Ecto.Changeset.change(
      last_seen_at: now,
      expires_at: DateTime.add(now, ttl_days * 24 * 60 * 60)
    )
    |> Repo.update!()
  end

  def revoke_session(session_id) when is_binary(session_id) do
    now = DateTime.truncate(now(), :second)

    Repo.update_all(
      from(s in Session, where: s.id == ^session_id and is_nil(s.revoked_at)),
      set: [revoked_at: now]
    )

    :ok
  end

  def revoke_session(_), do: :ok

  ## Auth events

  def record_event(event_type, attrs \\ %{}) do
    # Schemaless insert_all — encode the payload map explicitly (SQLite
    # stores JSON as TEXT and the schemaless path has no :map type info).
    payload = if attrs[:payload], do: Jason.encode!(attrs[:payload])

    Repo.insert_all("auth_events", [
      %{
        occurred_at: DateTime.truncate(now(), :second),
        didi_id: attrs[:didi_id],
        app_slug: attrs[:app_slug],
        org_id: attrs[:org_id],
        event_type: event_type,
        payload: payload
      }
    ])

    :ok
  end

  ## Helpers

  defp hash(raw), do: :crypto.hash(:sha256, raw)
  defp now, do: DateTime.utc_now()

  defp config(key, default) do
    Application.get_env(:id_didi_sh, :identity, []) |> Keyword.get(key, default)
  end
end
