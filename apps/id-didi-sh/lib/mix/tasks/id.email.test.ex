defmodule Mix.Tasks.Id.Email.Test do
  @shortdoc "Send a real test email through the configured adapter"

  @moduledoc """
  Usage: `set -a; source .env; set +a; mix id.email.test you@example.com`

  Sends a test message through whatever mailer runtime.exs resolved —
  with RESEND_API_KEY in the env, that's the Resend adapter for real.
  Sender: EMAIL_FROM if set, else onboarding@resend.dev (the only
  allowed sender until the didi.sh domain is verified in Resend).
  """

  use Mix.Task

  import Swoosh.Email

  @impl true
  def run([to]) do
    Mix.Task.run("app.start")

    from = System.get_env("EMAIL_FROM") || "onboarding@resend.dev"

    result =
      new()
      |> to(to)
      |> from({"didi.sh", from})
      |> subject("didi.sh test — the email pipe works")
      |> text_body("""
      This is a test send from the didi.sh identity service.

      Adapter live. Magic links will look like this, but with a link.
      """)
      |> IdDidiSh.Mailer.deliver()

    case result do
      {:ok, meta} -> Mix.shell().info("sent ✓ #{inspect(meta)}")
      {:error, reason} -> Mix.shell().error("send failed: #{inspect(reason)}")
    end
  end

  def run(_), do: Mix.shell().error("usage: mix id.email.test <to-address>")
end
