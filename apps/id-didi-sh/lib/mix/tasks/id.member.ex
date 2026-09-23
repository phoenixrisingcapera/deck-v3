defmodule Mix.Tasks.Id.Member do
  @shortdoc "Upsert a membership: user × org → role"

  @moduledoc """
  Usage: `mix id.member <email-or-didi_id> <org-domain> <role>`

  Roles: #{Enum.join(IdDidiSh.Accounts.Membership.roles(), " | ")}

  Example: `mix id.member mpstaton@gmail.com lossless.group superuser`

  Upsert-by-natural-key: re-running with a different role updates the
  membership, never duplicates it.
  """

  use Mix.Task

  alias IdDidiSh.Accounts

  @impl true
  def run([who, org_id, role]) do
    Mix.Task.run("app.start")

    user = Accounts.get_user_by_email(who) || Accounts.get_user(who)

    case user do
      nil ->
        Mix.shell().error("no user found for #{who}")

      user ->
        case Accounts.upsert_membership(user.didi_id, org_id, role) do
          {:ok, m} ->
            Mix.shell().info("#{user.primary_email} → #{m.org_id} as #{m.role}")

          {:error, reason} ->
            Mix.shell().error("failed: #{reason}")
        end
    end
  end

  def run(_), do: Mix.shell().error("usage: mix id.member <email-or-didi_id> <org-domain> <role>")
end
