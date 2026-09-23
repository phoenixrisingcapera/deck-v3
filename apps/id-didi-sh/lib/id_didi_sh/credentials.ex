defmodule IdDidiSh.Credentials do
  @moduledoc """
  Credentials people lend to entities.

  The one rule that shapes every function here: **an entity never owns a
  credential.** A person lends one and keeps title throughout. Ending the loan
  takes the key back; the entity keeps everything it made with it.

  Two invariants, held firmly because they are what makes "lending" mean lending
  rather than giving away:

  1. **A borrower can never read the value.** No function here returns plaintext
     except `resolve/4` (increment 5), which is authenticated as a registered
     server-side app, not as a person. `render/1` is the only serializer, and it
     structurally cannot emit the value.
  2. **Every use is attributed.** Without it the lender cannot make an informed
     decision about staying lent, so the rational move becomes never lending.

  A **cascade** is one lending act naming several entities; the loans under it
  are one per entity. The spend cap lives on the cascade because that is the
  lender's exposure on one card; usage is attributed per entity because that is
  the breakdown they need to read.
  """

  import Ecto.Query

  alias IdDidiSh.Repo
  alias IdDidiSh.UUID7
  alias IdDidiSh.Accounts
  alias IdDidiSh.Credentials.{Credential, Cascade, Loan, Usage}
  alias IdDidiSh.Entities.Entity

  @providers ~w(anthropic openai google decile streak firecrawl tavily other)

  def providers, do: @providers

  @doc """
  Store a credential owned by a person.

  The raw value is encrypted at rest by `IdDidiSh.Vault`. `last_four` is kept in
  plaintext so a human can tell two keys apart without ever seeing either.
  """
  def create_credential(owner_didi_id, provider, label, raw_value)
      when is_binary(raw_value) do
    cond do
      provider not in @providers ->
        {:error, :invalid_provider}

      is_nil(Accounts.get_user(owner_didi_id)) ->
        {:error, :unknown_user}

      String.trim(raw_value) == "" ->
        {:error, :empty_value}

      is_nil(label) or String.trim(to_string(label)) == "" ->
        {:error, :label_required}

      true ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        Repo.insert(%Credential{
          id: UUID7.generate(),
          owner_didi_id: owner_didi_id,
          provider: provider,
          label: label,
          value_encrypted: raw_value,
          last_four: last_four(raw_value),
          inserted_at: now,
          updated_at: now
        })
    end
  end

  def create_credential(_, _, _, _), do: {:error, :empty_value}

  @doc "Credentials this person owns. Live ones first; revoked kept for the record."
  def list_credentials(owner_didi_id) do
    Repo.all(
      from c in Credential,
        where: c.owner_didi_id == ^owner_didi_id,
        order_by: [asc: c.revoked_at, desc: c.inserted_at]
    )
  end

  def get_credential(id) when is_binary(id), do: Repo.get(Credential, id)
  def get_credential(_), do: nil

  @doc """
  Revoke a credential. Only the owner may — it is their key.

  The row is kept rather than deleted so `credential_usage` stays meaningful:
  the lender's record of what their card paid for should survive the key.
  """
  def revoke_credential(id, by_didi_id) do
    case get_credential(id) do
      nil ->
        {:error, :not_found}

      %Credential{owner_didi_id: owner} when owner != by_didi_id ->
        {:error, :not_the_owner}

      %Credential{revoked_at: %DateTime{}} = c ->
        {:ok, c}

      credential ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        credential
        |> Ecto.Changeset.change(revoked_at: now, updated_at: now)
        |> Repo.update()
    end
  end

  def live?(%Credential{revoked_at: nil}), do: true
  def live?(%Credential{}), do: false

  ## Lending

  @doc """
  Lend a credential to one or more entities in a single act — a **cascade**.

  The lender need NOT be a member of any target: the person with the credit card
  is frequently not on the project (Ruling 2). A live loan confers derived
  `:admin` on them for as long as it lasts.

  `terms` accepts `:spend_cap` (minor units), `:cap_period` (`"day"` |
  `"month"`), `:expires_at`, `:wind_down_until`.
  """
  def lend(credential_id, entity_ids, terms \\ %{}, lent_by)

  def lend(_credential_id, [], _terms, _lent_by), do: {:error, :no_entities}

  def lend(credential_id, entity_ids, terms, lent_by) when is_list(entity_ids) do
    entity_ids = Enum.uniq(entity_ids)

    cond do
      is_nil(get_credential(credential_id)) ->
        {:error, :unknown_credential}

      not live?(get_credential(credential_id)) ->
        {:error, :credential_revoked}

      get_credential(credential_id).owner_didi_id != lent_by ->
        # You cannot lend someone else's key. Title never moves.
        {:error, :not_the_owner}

      Enum.any?(entity_ids, &is_nil(IdDidiSh.Entities.get_entity(&1))) ->
        {:error, :unknown_entity}

      not valid_period?(terms) ->
        {:error, :invalid_cap_period}

      true ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        cascade = %Cascade{
          id: UUID7.generate(),
          credential_id: credential_id,
          lent_by: lent_by,
          lent_at: now,
          spend_cap: Map.get(terms, :spend_cap),
          cap_period: Map.get(terms, :cap_period),
          expires_at: Map.get(terms, :expires_at),
          wind_down_until: Map.get(terms, :wind_down_until),
          inserted_at: now,
          updated_at: now
        }

        {:ok, cascade} = Repo.insert(cascade)

        loans =
          Enum.map(entity_ids, fn entity_id ->
            {:ok, loan} =
              Repo.insert(%Loan{
                id: UUID7.generate(),
                cascade_id: cascade.id,
                entity_id: entity_id,
                inserted_at: now,
                updated_at: now
              })

            loan
          end)

        {:ok, cascade, loans}
    end
  end

  @doc """
  End an entire cascade — "they take their keys". Every loan in it ends at once.
  """
  def end_cascade(cascade_id, by_didi_id) do
    case Repo.get(Cascade, cascade_id) do
      nil ->
        {:error, :not_found}

      %Cascade{lent_by: lender} when lender != by_didi_id ->
        {:error, :not_the_lender}

      %Cascade{ended_at: %DateTime{}} = c ->
        {:ok, c}

      cascade ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        Repo.update_all(
          from(l in Loan, where: l.cascade_id == ^cascade_id and is_nil(l.ended_at)),
          set: [ended_at: now, updated_at: now]
        )

        cascade
        |> Ecto.Changeset.change(ended_at: now, updated_at: now)
        |> Repo.update()
    end
  end

  @doc """
  End ONE entity's loan while the rest of the cascade survives — partial
  withdrawal, for when one collaboration sours and the others do not.
  """
  def end_loan(cascade_id, entity_id, by_didi_id) do
    case Repo.get(Cascade, cascade_id) do
      nil ->
        {:error, :not_found}

      %Cascade{lent_by: lender} when lender != by_didi_id ->
        {:error, :not_the_lender}

      _cascade ->
        now = DateTime.utc_now() |> DateTime.truncate(:second)

        case Repo.update_all(
               from(l in Loan,
                 where:
                   l.cascade_id == ^cascade_id and l.entity_id == ^entity_id and
                     is_nil(l.ended_at)
               ),
               set: [ended_at: now, updated_at: now]
             ) do
          {1, _} -> :ok
          _ -> {:error, :no_live_loan}
        end
    end
  end

  @doc """
  Live loans reaching an entity, newest lending act first.

  "Live" means: the loan has not ended, its cascade has not ended or expired,
  and the credential behind it has not been revoked. All four can end a loan
  independently, which is why this is one query rather than four checks
  scattered across callers.
  """
  def live_loans_for_entity(entity_id) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    Repo.all(
      from l in Loan,
        join: c in Cascade,
        on: c.id == l.cascade_id,
        join: cr in Credential,
        on: cr.id == c.credential_id,
        where:
          l.entity_id == ^entity_id and is_nil(l.ended_at) and is_nil(c.ended_at) and
            is_nil(cr.revoked_at) and (is_nil(c.expires_at) or c.expires_at > ^now),
        order_by: [desc: c.lent_at],
        select: %{loan: l, cascade: c, credential: cr}
    )
  end

  @doc """
  Live loans FROM a credential — where is this key currently reaching?

  The mirror of `live_loans_for_entity/1`, and the same four-way liveness
  join: the loan has not ended, its cascade has not ended or expired, and the
  credential is not revoked. Joins the entity so a caller can name the place
  without a second query, and returns the cascade id because ending one loan
  needs it.
  """
  def live_loans_for_credential(credential_id) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    Repo.all(
      from l in Loan,
        join: c in Cascade,
        on: c.id == l.cascade_id,
        join: cr in Credential,
        on: cr.id == c.credential_id,
        join: e in Entity,
        on: e.id == l.entity_id,
        where:
          c.credential_id == ^credential_id and is_nil(l.ended_at) and is_nil(c.ended_at) and
            is_nil(cr.revoked_at) and (is_nil(c.expires_at) or c.expires_at > ^now),
        order_by: [desc: c.lent_at],
        select: %{entity: e, cascade_id: c.id, lent_at: c.lent_at, spend_cap: c.spend_cap}
    )
  end

  @doc """
  Does this person have a live loan to this entity? The basis of derived admin.
  """
  def lender?(entity_id, didi_id) do
    entity_id
    |> live_loans_for_entity()
    |> Enum.any?(fn %{cascade: c} -> c.lent_by == didi_id end)
  end

  @doc "Entities this person currently lends to — access without membership."
  def entities_lent_to(didi_id) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    Repo.all(
      from l in Loan,
        join: c in Cascade,
        on: c.id == l.cascade_id,
        join: cr in Credential,
        on: cr.id == c.credential_id,
        where:
          c.lent_by == ^didi_id and is_nil(l.ended_at) and is_nil(c.ended_at) and
            is_nil(cr.revoked_at) and (is_nil(c.expires_at) or c.expires_at > ^now),
        select: l.entity_id,
        distinct: true
    )
  end

  ## Resolve — the only path that returns plaintext

  @doc """
  Hand a lent credential's value to a **registered server-side app** acting for
  an entity, and record the use.

  This is the single exception to "nobody reads the value", and the boundary is
  deliberate: Ruling 3's invariant is that a *borrower* — a human — never sees
  it. A registered app is not a borrower. A browser must never reach this, which
  is why the endpoint in front of it refuses cookie auth outright.

  `opts`: `:didi_id` (the person on whose behalf the app is acting, if any),
  `:units`, `:cost_estimate`.

  Returns `{:ok, plaintext}` or `{:error, reason}` where reason is
  `:no_live_loan` or `:cap_exceeded`.
  """
  def resolve(entity_id, provider, app_slug, opts \\ []) do
    case live_loans_for_entity(entity_id) |> Enum.filter(&(&1.credential.provider == provider)) do
      [] ->
        {:error, :no_live_loan}

      [match | rest] ->
        # More than one live loan for the same provider is a genuine ambiguity a
        # human created — there is no hierarchy to disambiguate it (Ruling 1).
        # Take the most recent (live_loans_for_entity orders by lent_at desc)
        # and make the ambiguity visible rather than silently arbitrary.
        if rest != [] do
          require Logger

          Logger.warning(
            "multiple live #{provider} loans for entity #{entity_id}; using cascade #{match.cascade.id}"
          )
        end

        record_and_return(match, entity_id, app_slug, opts)
    end
  end

  defp record_and_return(
         %{loan: loan, cascade: cascade, credential: credential},
         entity_id,
         app_slug,
         opts
       ) do
    if cap_exceeded?(cascade) do
      {:error, :cap_exceeded}
    else
      {:ok, _} =
        record_usage(loan.id, %{
          credential_id: credential.id,
          cascade_id: cascade.id,
          entity_id: entity_id,
          didi_id: Keyword.get(opts, :didi_id),
          app_slug: app_slug,
          units: Keyword.get(opts, :units),
          cost_estimate: Keyword.get(opts, :cost_estimate)
        })

      {:ok, credential.value_encrypted}
    end
  end

  @doc "Append a usage row. Append-only: never updated, never deleted."
  def record_usage(loan_id, attrs) do
    now = DateTime.utc_now() |> DateTime.truncate(:second)

    Repo.insert(%Usage{
      loan_id: loan_id,
      credential_id: attrs[:credential_id],
      cascade_id: attrs[:cascade_id],
      entity_id: attrs[:entity_id],
      didi_id: attrs[:didi_id],
      app_slug: attrs[:app_slug],
      units: attrs[:units],
      cost_estimate: attrs[:cost_estimate],
      occurred_at: now,
      inserted_at: now,
      updated_at: now
    })
  end

  @doc """
  Spend recorded against a cascade in its current cap period.

  The cap is on the cascade, not the loan, because it is the lender's exposure
  on one card across everywhere they lent.
  """
  def spend_in_period(%Cascade{spend_cap: nil}), do: 0

  def spend_in_period(%Cascade{} = cascade) do
    since = period_start(cascade.cap_period)

    Repo.one(
      from u in Usage,
        where: u.cascade_id == ^cascade.id and u.occurred_at >= ^since,
        select: coalesce(sum(u.cost_estimate), 0)
    ) || 0
  end

  @doc "Per-entity breakdown of what a credential was spent on — the meter."
  def usage_for_credential(credential_id) do
    Repo.all(
      from u in Usage,
        where: u.credential_id == ^credential_id,
        group_by: u.entity_id,
        select: %{
          entity_id: u.entity_id,
          calls: count(u.id),
          units: coalesce(sum(u.units), 0),
          cost_estimate: coalesce(sum(u.cost_estimate), 0)
        }
    )
  end

  defp cap_exceeded?(%Cascade{spend_cap: nil}), do: false

  defp cap_exceeded?(%Cascade{spend_cap: cap} = cascade),
    do: spend_in_period(cascade) >= cap

  defp period_start(nil), do: ~U[1970-01-01 00:00:00Z]

  defp period_start("day"),
    do: DateTime.utc_now() |> DateTime.add(-24 * 3600) |> DateTime.truncate(:second)

  defp period_start("month"),
    do: DateTime.utc_now() |> DateTime.add(-30 * 24 * 3600) |> DateTime.truncate(:second)

  defp valid_period?(terms) do
    case Map.get(terms, :cap_period) do
      nil -> true
      p -> p in Cascade.periods()
    end
  end

  @doc """
  The ONLY serializer for a credential.

  Deliberately built by naming safe fields rather than by dropping unsafe ones:
  a future field is invisible until someone adds it here, which is the failure
  direction you want.
  """
  def render(%Credential{} = c) do
    %{
      id: c.id,
      provider: c.provider,
      label: c.label,
      last_four: c.last_four,
      owner_didi_id: c.owner_didi_id,
      revoked_at: c.revoked_at,
      created_at: c.inserted_at
    }
  end

  # Enough to recognise a key, not enough to use one. Short values are masked
  # entirely rather than half-shown.
  defp last_four(value) do
    trimmed = String.trim(value)
    if String.length(trimmed) < 8, do: "····", else: String.slice(trimmed, -4, 4)
  end
end
