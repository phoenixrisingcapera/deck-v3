defmodule IdDidiSh.Accounts.InviteNotifier do
  @moduledoc """
  Invite email delivery, from `no-reply@didi.sh` via Resend.

  Separate from `MagicLinkNotifier` because the two say different things to a
  person: a magic link is "sign back in", an invite is "someone added you to
  something you have never seen." Same token table, same single-use discipline,
  different words.

  The mail goes out through whatever Swoosh adapter is configured — the Resend
  adapter in production, the Local mailbox in dev — so this module never knows
  about Resend directly.
  """

  import Swoosh.Email

  alias IdDidiSh.Mailer

  def deliver(email, raw_token, opts \\ []) do
    identity = Application.get_env(:id_didi_sh, :identity, [])
    issuer = Keyword.get(identity, :issuer, "https://id.didi.sh")
    from_addr = Keyword.get(identity, :email_from, "no-reply@didi.sh")

    entity_name = Keyword.get(opts, :entity_name)
    inviter = Keyword.get(opts, :inviter_name)

    intro =
      case {inviter, entity_name} do
        {nil, nil} -> "You have been invited to didi.sh."
        {nil, name} -> "You have been invited to join #{name}."
        {who, nil} -> "#{who} invited you to didi.sh."
        {who, name} -> "#{who} invited you to join #{name}."
      end

    new()
    |> to(email)
    |> from({"didi.sh", from_addr})
    |> subject(subject_for(entity_name))
    |> text_body("""
    #{intro}

    Accept with this single-use link (expires in 7 days):

    #{issuer}/access?token=#{raw_token}

    Opening the link creates your account — there is no password to choose and
    nothing to install.

    If you weren't expecting this, ignore it. Nothing happens without the link.
    """)
    |> Mailer.deliver()
  end

  defp subject_for(nil), do: "You've been invited to didi.sh"
  defp subject_for(name), do: "You've been invited to #{name}"
end
