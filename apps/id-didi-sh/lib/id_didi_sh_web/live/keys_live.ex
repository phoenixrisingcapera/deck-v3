defmodule IdDidiShWeb.KeysLive do
  @moduledoc """
  The lender's screen at `/keys`.

  This is the increment the whole model exists for. The persona will click a
  link and paste one value into one labelled field; they will not open a
  terminal, and a path that requires one fails on week two even when it works on
  day one. Everything before this increment was reachable only by HTTP client.

  Two rules the markup enforces:

  1. **The value is write-only.** It goes in once and is never rendered back —
     not masked, not behind a reveal. `last_four` is the only hint.
  2. **The lending consequence is visible BEFORE confirming** (Ruling 2b). A
     loan follows the entity, so it reaches whoever joins later. A lender who
     learns that afterwards never lends again.
  """

  use IdDidiShWeb, :live_view

  alias IdDidiSh.{Accounts, Credentials, Entities}
  alias IdDidiSh.Token

  @impl true
  def mount(_params, session, socket) do
    case current_user(session) do
      nil ->
        {:ok,
         socket
         |> put_flash(:error, "Sign in to manage your keys.")
         |> redirect(to: ~p"/access")}

      user ->
        {:ok, socket |> assign(:user, user) |> assign_defaults() |> load()}
    end
  end

  defp assign_defaults(socket) do
    socket
    |> assign(:provider, "anthropic")
    |> assign(:label, "")
    |> assign(:value, "")
    |> assign(:lending, nil)
    |> assign(:selected, MapSet.new())
    |> assign(:spend_cap, "")
    |> assign(:cap_period, "month")
    |> assign(:new_entity_name, "")
    |> assign(:new_entity_kind, "project")
  end

  defp load(socket) do
    user = socket.assigns.user

    credentials = Credentials.list_credentials(user.didi_id)

    socket
    |> assign(:credentials, credentials)
    |> assign(:entities, Entities.list_entities_for(user.didi_id))
    |> assign(
      :loans,
      Map.new(credentials, fn c -> {c.id, Credentials.live_loans_for_credential(c.id)} end)
    )
  end

  ## Events

  @impl true
  def handle_event("form_change", params, socket) do
    {:noreply,
     socket
     |> assign(:provider, params["provider"] || socket.assigns.provider)
     |> assign(:label, params["label"] || "")
     |> assign(:value, params["value"] || "")}
  end

  def handle_event("paste", %{"provider" => p, "label" => l, "value" => v}, socket) do
    case Credentials.create_credential(socket.assigns.user.didi_id, p, l, v) do
      {:ok, _} ->
        {:noreply,
         socket
         |> put_flash(:info, "Key stored. Nobody can read it back — not even you.")
         |> assign_defaults()
         |> load()}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, humanize(reason))}
    end
  end

  def handle_event("start_lending", %{"id" => id}, socket) do
    {:noreply, socket |> assign(:lending, id) |> assign(:selected, MapSet.new())}
  end

  def handle_event("cancel_lending", _, socket) do
    {:noreply, assign(socket, :lending, nil)}
  end

  # Taking a key back from ONE place, as opposed to everywhere. Separate from
  # revoke on purpose — they are different intentions and should be hard to
  # confuse at three in the morning.
  def handle_event("end_loan", %{"cascade" => cascade_id, "entity" => entity_id}, socket) do
    case Credentials.end_loan(cascade_id, entity_id, socket.assigns.user.didi_id) do
      :ok ->
        {:noreply, socket |> load() |> put_flash(:info, "Taken back.")}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, humanize(reason))}
    end
  end

  def handle_event("new_entity_change", params, socket) do
    {:noreply,
     socket
     |> assign(:new_entity_name, params["name"] || "")
     |> assign(:new_entity_kind, params["kind"] || socket.assigns.new_entity_kind)}
  end

  # A lender who is in nothing yet has nowhere to lend to. Rather than send
  # them to an API they cannot call from a browser, they name a place here and
  # it is created, owned by them, and pre-selected to lend to.
  def handle_event("create_entity", params, socket) do
    # Read the submitted fields rather than the last change event — a submit
    # carries them, and relying on assigns loses the name when a form is
    # submitted without an intervening change.
    name = (params["name"] || socket.assigns.new_entity_name) |> String.trim()
    kind = params["kind"] || socket.assigns.new_entity_kind
    user = socket.assigns.user

    if name == "" do
      {:noreply, put_flash(socket, :error, "Give it a name first.")}
    else
      case Entities.create_entity(%{kind: kind, slug: slugify(name), name: name}) do
        {:ok, entity} ->
          # The creator owns what they created — otherwise an entity is born
          # with nobody able to administer it.
          {:ok, _} =
            Entities.add_member(entity.id, user.didi_id, "org_owner",
              via: "seed",
              granted_by: user.didi_id
            )

          {:noreply,
           socket
           |> assign(:new_entity_name, "")
           |> assign(:selected, MapSet.put(socket.assigns.selected, entity.id))
           |> load()
           |> put_flash(:info, "Created #{entity.name}.")}

        {:error, :slug_taken} ->
          {:noreply,
           put_flash(socket, :error, "There is already one called that. Try another name.")}

        {:error, reason} ->
          {:noreply, put_flash(socket, :error, humanize(reason))}
      end
    end
  end

  def handle_event("toggle_entity", %{"id" => id}, socket) do
    selected = socket.assigns.selected

    selected =
      if MapSet.member?(selected, id),
        do: MapSet.delete(selected, id),
        else: MapSet.put(selected, id)

    {:noreply, assign(socket, :selected, selected)}
  end

  def handle_event("terms_change", params, socket) do
    {:noreply,
     socket
     |> assign(:spend_cap, params["spend_cap"] || "")
     |> assign(:cap_period, params["cap_period"] || "month")}
  end

  def handle_event("lend", _params, socket) do
    ids = MapSet.to_list(socket.assigns.selected)

    terms =
      case Integer.parse(to_string(socket.assigns.spend_cap)) do
        {cap, _} when cap > 0 -> %{spend_cap: cap, cap_period: socket.assigns.cap_period}
        _ -> %{}
      end

    case Credentials.lend(socket.assigns.lending, ids, terms, socket.assigns.user.didi_id) do
      {:ok, _cascade, loans} ->
        {:noreply,
         socket
         |> put_flash(:info, "Lent to #{length(loans)} #{noun(length(loans))}.")
         |> assign(:lending, nil)
         |> load()}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, humanize(reason))}
    end
  end

  def handle_event("revoke", %{"id" => id}, socket) do
    case Credentials.revoke_credential(id, socket.assigns.user.didi_id) do
      {:ok, _} ->
        {:noreply,
         socket
         |> put_flash(:info, "Key revoked. Everything made with it stays where it is.")
         |> load()}

      {:error, reason} ->
        {:noreply, put_flash(socket, :error, humanize(reason))}
    end
  end

  ## Render

  @impl true
  def render(assigns) do
    ~H"""
    <div class="mx-auto max-w-3xl p-6 space-y-8">
      <header>
        <h1 class="text-2xl font-semibold">Your keys</h1>
        <p class="text-sm opacity-70">
          Keys stay yours. Lend one to a project and take it back whenever you like —
          the work made with it stays put.
        </p>
      </header>

      <%!-- Flash renders here rather than in a layout: this LiveView has none,
            and without it a failed paste would silently do nothing. --%>
      <div
        :if={Phoenix.Flash.get(@flash, :info)}
        class="rounded border border-success/40 bg-success/10 p-3 text-sm"
      >
        {Phoenix.Flash.get(@flash, :info)}
      </div>
      <div
        :if={Phoenix.Flash.get(@flash, :error)}
        class="rounded border border-error/40 bg-error/10 p-3 text-sm"
      >
        {Phoenix.Flash.get(@flash, :error)}
      </div>

      <section class="rounded border border-base-300 bg-base-200 p-4 space-y-3">
        <h2 class="font-medium">Add a key</h2>
        <form id="paste-key" phx-submit="paste" phx-change="form_change" class="space-y-3">
          <select name="provider" class="select w-full">
            <option :for={p <- Credentials.providers()} value={p} selected={p == @provider}>
              {p}
            </option>
          </select>
          <input
            name="label"
            value={@label}
            placeholder="What is this? e.g. Jason's Anthropic card"
            class="input w-full"
          />
          <input
            name="value"
            value={@value}
            type="password"
            placeholder="Paste the key"
            autocomplete="off"
            class="input w-full"
          />
          <p class="text-xs opacity-60">
            Stored encrypted. It is never shown again — you will only see the last four characters.
          </p>
          <button class="btn btn-primary">Store it</button>
        </form>
      </section>

      <section class="space-y-3">
        <h2 class="font-medium">Stored</h2>
        <p :if={@credentials == []} class="text-sm opacity-60">Nothing yet.</p>

        <div :for={c <- @credentials} class="rounded border border-base-300 bg-base-200 p-4 space-y-2">
          <div class="flex items-center justify-between">
            <div>
              <span class="font-medium">{c.label}</span>
              <span class="mono text-sm opacity-60">· {c.provider} · ····{c.last_four}</span>
              <span :if={c.revoked_at} class="stamp" data-ink="dim">revoked</span>
            </div>
            <div :if={is_nil(c.revoked_at)} class="space-x-2">
              <button phx-click="start_lending" phx-value-id={c.id} class="btn btn-sm btn-outline">
                Lend
              </button>
              <button phx-click="revoke" phx-value-id={c.id} class="btn btn-sm btn-outline">
                Take it back
              </button>
            </div>
          </div>

          <%!-- Where this key currently reaches. Without it a lender has no
                way to see whether the lend they just made actually landed. --%>
          <div :if={@loans[c.id] not in [nil, []]} class="flex flex-wrap items-center gap-2">
            <span class="eyebrow">Lent to</span>
            <span
              :for={loan <- @loans[c.id]}
              class="inline-flex items-center gap-2 rounded border border-success/40 bg-success/10 px-2 py-1 text-sm"
            >
              <span>{loan.entity.name}</span>
              <span class="mono opacity-50">{loan.entity.kind}</span>
              <button
                phx-click="end_loan"
                phx-value-cascade={loan.cascade_id}
                phx-value-entity={loan.entity.id}
                class="opacity-60 hover:opacity-100"
                aria-label={"Take back from #{loan.entity.name}"}
                title={"Take back from #{loan.entity.name}"}
              >
                ×
              </button>
            </span>
          </div>

          <p
            :if={is_nil(c.revoked_at) and @loans[c.id] in [nil, []]}
            class="text-sm opacity-50"
          >
            Not lent anywhere yet.
          </p>

          <div :if={@lending == c.id} class="rounded border border-base-300 bg-base-300 p-3 space-y-3">
            <p class="text-sm font-medium">Lend to which?</p>
            <p :if={@entities == []} class="text-sm opacity-60">
              You are not in any yet — name one below and it is yours.
            </p>
            <label :for={e <- @entities} class="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={MapSet.member?(@selected, e.id)}
                phx-click="toggle_entity"
                phx-value-id={e.id}
                class="checkbox checkbox-sm"
              />
              <span>{e.name} <span class="opacity-50">({e.kind})</span></span>
            </label>

            <form
              id={"new-entity-#{c.id}"}
              phx-change="new_entity_change"
              phx-submit="create_entity"
              class="flex flex-wrap items-center gap-2 border-t border-base-content/10 pt-3 text-sm"
            >
              <input
                name="name"
                value={@new_entity_name}
                placeholder="Name a new one"
                class="input input-sm flex-1 min-w-40"
              />
              <select name="kind" class="select select-sm">
                <option :for={k <- Entities.Entity.kinds()} value={k} selected={k == @new_entity_kind}>
                  {k}
                </option>
              </select>
              <button type="submit" class="btn btn-sm btn-outline">Create</button>
            </form>

            <form id={"terms-#{c.id}"} phx-change="terms_change" class="flex gap-2 text-sm">
              <input
                name="spend_cap"
                value={@spend_cap}
                placeholder="Spend cap (optional, in cents)"
                class="input flex-1"
              />
              <select name="cap_period" class="select">
                <option value="month" selected={@cap_period == "month"}>per month</option>
                <option value="day" selected={@cap_period == "day"}>per day</option>
              </select>
            </form>

            <p
              :if={MapSet.size(@selected) > 0}
              class="rounded border border-warning/40 bg-warning/10 p-2 text-sm"
            >
              This lends to everyone in {MapSet.size(@selected)} {noun(MapSet.size(@selected))}, <strong>including anyone added later</strong>. You can take it back at any time.
            </p>

            <div class="space-x-2">
              <button
                phx-click="lend"
                disabled={MapSet.size(@selected) == 0}
                class="btn btn-primary disabled:opacity-40"
              >
                Lend it
              </button>
              <button phx-click="cancel_lending" class="btn btn-ghost">Cancel</button>
            </div>
          </div>
        </div>
      </section>
    </div>
    """
  end

  ## Helpers

  defp current_user(session) do
    with token when is_binary(token) <- session["didi_token"],
         {:ok, claims} <- Token.verify(token),
         s when not is_nil(s) <- Accounts.get_live_session(claims.session_id) do
      Accounts.get_user(claims.didi_id)
    else
      _ -> nil
    end
  end

  defp noun(1), do: "place"
  defp noun(_), do: "places"

  # Error atoms are for programs. People get sentences.
  defp humanize(:invalid_provider), do: "Pick a provider from the list."
  defp humanize(:empty_value), do: "Paste the key before storing it."
  defp humanize(:label_required), do: "Give it a name so you can tell it apart later."
  defp humanize(:not_the_owner), do: "That key is not yours."
  defp humanize(:not_the_lender), do: "Only whoever lent it can take it back."
  defp humanize(:no_entities), do: "Pick at least one place to lend it to."
  defp humanize(:credential_revoked), do: "That key has been taken back already."
  defp humanize(other), do: "Something went wrong: #{other}"

  # Entities take slugs raw and only reject exact duplicates, so the browser
  # path normalises rather than handing the user a slug field to get wrong.
  defp slugify(name) do
    name
    |> String.downcase()
    |> String.replace(~r/[^a-z0-9]+/u, "-")
    |> String.trim("-")
  end
end
