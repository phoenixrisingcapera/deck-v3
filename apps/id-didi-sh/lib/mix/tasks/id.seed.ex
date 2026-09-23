defmodule Mix.Tasks.Id.Seed do
  @shortdoc "Seed a user (invite-only stand-in until increment 3's invites)"

  @moduledoc """
  Usage: `mix id.seed alice@example.com "Alice Example"`

  Creates a user directly. This is the walking skeleton's stand-in for
  invite redemption (increment 3) — magic links only authenticate
  existing users, so dev needs a way to have one.
  """

  use Mix.Task

  @impl true
  def run(args) do
    Mix.Task.run("app.start")

    case args do
      [email | rest] ->
        name = if rest == [], do: nil, else: Enum.join(rest, " ")

        case IdDidiSh.Accounts.create_user(%{primary_email: email, name: name}) do
          {:ok, user} ->
            Mix.shell().info("created #{user.primary_email} didi_id=#{user.didi_id}")

          {:error, changeset} ->
            Mix.shell().error("failed: #{inspect(changeset.errors)}")
        end

      _ ->
        Mix.shell().error("usage: mix id.seed <email> [name]")
    end
  end
end
