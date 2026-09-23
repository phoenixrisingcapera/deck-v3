defmodule IdDidiSh.Mailer.ResendAdapter do
  @moduledoc """
  Minimal Swoosh adapter for Resend (https://resend.com) over Req.

  Hand-rolled (~40 lines) instead of the `resend` hex package, which
  pins hackney and conflicts with this app's lockfile — Resend's send
  API is one JSON POST, and Req is already a dependency. Configured in
  runtime.exs when RESEND_API_KEY is present; dev without the key stays
  on Swoosh.Adapters.Local (mailbox at /dev/mailbox).

  Until the didi.sh domain is verified in Resend, sends must originate
  from onboarding@resend.dev — override the sender via EMAIL_FROM.
  """

  use Swoosh.Adapter, required_config: [:api_key]

  @endpoint "https://api.resend.com/emails"

  @impl true
  def deliver(%Swoosh.Email{} = email, config) do
    payload =
      %{
        "from" => format(email.from),
        "to" => Enum.map(email.to, &format/1),
        "subject" => email.subject,
        "text" => email.text_body,
        "html" => email.html_body,
        "reply_to" => email.reply_to && format(email.reply_to)
      }
      |> Enum.reject(fn {_k, v} -> is_nil(v) end)
      |> Map.new()

    case Req.post(@endpoint,
           json: payload,
           auth: {:bearer, Keyword.fetch!(config, :api_key)},
           retry: false
         ) do
      {:ok, %{status: status, body: body}} when status in 200..299 -> {:ok, body}
      {:ok, %{status: status, body: body}} -> {:error, {status, body}}
      {:error, reason} -> {:error, reason}
    end
  end

  defp format({name, address}) when name in [nil, ""], do: address
  defp format({name, address}), do: "#{name} <#{address}>"
  defp format(address) when is_binary(address), do: address
end
