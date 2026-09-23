defmodule Mix.Tasks.Id.Alias do
  @shortdoc "Attach an alt email to an existing user (one didi_id, many addresses)"

  @moduledoc """
  Usage: `mix id.alias <existing-email-or-didi_id> <new-alt-email>`

  Resolves the user by any of their current addresses (or didi_id) and
  attaches the new address as an alias. Magic links to any alias
  authenticate the same identity.
  """

  use Mix.Task

  alias IdDidiSh.Accounts

  @impl true
  def run([who, alt]) do
    Mix.Task.run("app.start")

    user = Accounts.get_user_by_email(who) || Accounts.get_user(who)

    case user do
      nil ->
        Mix.shell().error("no user found for #{who}")

      user ->
        case Accounts.add_email_alias(user, alt) do
          {:ok, email} ->
            aliases = Accounts.list_email_aliases(user.didi_id)

            Mix.shell().info(
              "#{email} → #{user.primary_email} (didi_id=#{user.didi_id}); aliases: #{Enum.join(aliases, ", ")}"
            )

          {:error, reason} ->
            Mix.shell().error("failed: #{reason}")
        end
    end
  end

  def run(_), do: Mix.shell().error("usage: mix id.alias <existing-email-or-didi_id> <alt-email>")
end
