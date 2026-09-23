defmodule Mix.Tasks.Id.Entity do
  @shortdoc "Create an entity, or add a member to one"

  @moduledoc """
  Usage:

      mix id.entity new <kind> <slug> <display name...>
      mix id.entity add <slug> <email> <role>
      mix id.entity ls [slug]

  Examples:

      mix id.entity new project apollo Apollo Program
      mix id.entity add apollo alice@example.com editor
      mix id.entity ls apollo

  `kind` is one of organization | workspace | project and is a **display
  label** — entities are flat, with no containment and no inheritance.

  `role` uses the shared lattice: superuser | org_owner | org_admin | editor |
  viewer.

  Removal is deliberately not exposed here: it has to show the person what
  access survives (Ruling 1b), which is a conversation, not a one-liner.
  """

  use Mix.Task

  alias IdDidiSh.{Accounts, Entities}

  @impl true
  def run(["new", kind, slug | name_parts]) when name_parts != [] do
    Mix.Task.run("app.start")

    case Entities.create_entity(%{kind: kind, slug: slug, name: Enum.join(name_parts, " ")}) do
      {:ok, e} ->
        Mix.shell().info("entity #{e.id}  #{e.kind}/#{e.slug}  #{e.name}")

      {:error, reason} ->
        Mix.raise("could not create entity: #{inspect(reason)}")
    end
  end

  def run(["add", slug, email, role]) do
    Mix.Task.run("app.start")

    with %{} = entity <- Entities.get_entity_by_slug(slug) || {:error, :unknown_entity},
         %{} = user <- Accounts.get_user_by_email(email) || {:error, :unknown_user},
         {:ok, m} <- Entities.add_member(entity.id, user.didi_id, role, via: "seed") do
      Mix.shell().info("#{email} is #{m.role} in #{entity.kind}/#{entity.slug}")
    else
      {:error, reason} -> Mix.raise("could not add member: #{inspect(reason)}")
    end
  end

  def run(["ls"]) do
    Mix.Task.run("app.start")

    case Entities.list_entities() do
      [] -> Mix.shell().info("(no entities)")
      list -> Enum.each(list, &Mix.shell().info("#{&1.kind}/#{&1.slug}  #{&1.name}  #{&1.id}"))
    end
  end

  def run(["ls", slug]) do
    Mix.Task.run("app.start")

    case Entities.get_entity_by_slug(slug) do
      nil ->
        Mix.raise("no entity with slug #{slug}")

      entity ->
        Mix.shell().info("#{entity.kind}/#{entity.slug}  #{entity.name}  #{entity.id}")

        case Entities.list_members(entity.id) do
          [] ->
            Mix.shell().info("  (no members)")

          members ->
            Enum.each(members, fn m ->
              user = Accounts.get_user(m.didi_id)
              email = if user, do: user.primary_email, else: m.didi_id
              Mix.shell().info("  #{email}  #{m.role}  via=#{m.via}")
            end)
        end
    end
  end

  def run(_) do
    Mix.raise("""
    usage:
      mix id.entity new <kind> <slug> <display name...>
      mix id.entity add <slug> <email> <role>
      mix id.entity ls [slug]
    """)
  end
end
