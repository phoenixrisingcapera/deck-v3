defmodule Mix.Tasks.Id.Org do
  @shortdoc "Upsert an organization (domain-as-id)"

  @moduledoc """
  Usage: `mix id.org <domain> <display name...>`

  Example: `mix id.org humain.vc Humain VC`

  The domain IS the org id (locked convention). Idempotent — re-running
  updates the display name.
  """

  use Mix.Task

  @impl true
  def run([domain | name_parts]) when name_parts != [] do
    Mix.Task.run("app.start")

    case IdDidiSh.Accounts.upsert_org(domain, Enum.join(name_parts, " ")) do
      {:ok, org} -> Mix.shell().info("org #{org.id} (#{org.name}) slug=#{org.slug}")
      {:error, changeset} -> Mix.shell().error("failed: #{inspect(changeset.errors)}")
    end
  end

  def run(_), do: Mix.shell().error("usage: mix id.org <domain> <display name...>")
end
