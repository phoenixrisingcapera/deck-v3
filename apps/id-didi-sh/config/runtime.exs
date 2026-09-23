import Config

# config/runtime.exs is executed for all environments, including
# during releases. It is executed after compilation and before the
# system starts, so it is typically used to load production configuration
# and secrets from environment variables or elsewhere. Do not define
# any compile-time configuration in here, as it won't be applied.
# The block below contains prod specific runtime configuration.

# ## Using releases
#
# If you use `mix release`, you need to explicitly enable the server
# by passing the PHX_SERVER=true when you start it:
#
#     PHX_SERVER=true bin/id_didi_sh start
#
# Alternatively, you can use `mix phx.gen.release` to generate a `bin/server`
# script that automatically sets the env var above.
if System.get_env("PHX_SERVER") do
  config :id_didi_sh, IdDidiShWeb.Endpoint, server: true
end

config :id_didi_sh, IdDidiShWeb.Endpoint,
  http: [port: String.to_integer(System.get_env("PORT", "4000"))]

if config_env() == :prod do
  database_path =
    System.get_env("DATABASE_PATH") ||
      raise """
      environment variable DATABASE_PATH is missing.
      For example: /etc/id_didi_sh/id_didi_sh.db
      """

  config :id_didi_sh, IdDidiSh.Repo,
    database: database_path,
    pool_size: String.to_integer(System.get_env("POOL_SIZE") || "5")

  # The secret key base is used to sign/encrypt cookies and other secrets.
  # A default value is used in config/dev.exs and config/test.exs but you
  # want to use a different value for prod and you most likely don't want
  # to check this value into version control, so we use an environment
  # variable instead.
  secret_key_base =
    System.get_env("SECRET_KEY_BASE") ||
      raise """
      environment variable SECRET_KEY_BASE is missing.
      You can generate one by calling: mix phx.gen.secret
      """

  host = System.get_env("PHX_HOST") || "example.com"

  config :id_didi_sh, :dns_cluster_query, System.get_env("DNS_CLUSTER_QUERY")

  config :id_didi_sh, IdDidiShWeb.Endpoint,
    url: [host: host, port: 443, scheme: "https"],
    http: [
      # Enable IPv6 and bind on all interfaces.
      # Set it to  {0, 0, 0, 0, 0, 0, 0, 1} for local network only access.
      # See the documentation on https://bandit.hexdocs.pm/Bandit.html#t:options/0
      # for details about using IPv6 vs IPv4 and loopback vs public addresses.
      ip: {0, 0, 0, 0, 0, 0, 0, 0}
    ],
    secret_key_base: secret_key_base

  # ## SSL Support
  #
  # To get SSL working, you will need to add the `https` key
  # to your endpoint configuration:
  #
  #     config :id_didi_sh, IdDidiShWeb.Endpoint,
  #       https: [
  #         ...,
  #         port: 443,
  #         cipher_suite: :strong,
  #         keyfile: System.get_env("SOME_APP_SSL_KEY_PATH"),
  #         certfile: System.get_env("SOME_APP_SSL_CERT_PATH")
  #       ]
  #
  # The `cipher_suite` is set to `:strong` to support only the
  # latest and more secure SSL ciphers. This means old browsers
  # and clients may not be supported. You can set it to
  # `:compatible` for wider support.
  #
  # `:keyfile` and `:certfile` expect an absolute path to the key
  # and cert in disk or a relative path inside priv, for example
  # "priv/ssl/server.key". For all supported SSL configuration
  # options, see https://plug.hexdocs.pm/Plug.SSL.html#configure/1
  #
  # We also recommend setting `force_ssl` in your config/prod.exs,
  # ensuring no data is ever sent via http, always redirecting to https:
  #
  #     config :id_didi_sh, IdDidiShWeb.Endpoint,
  #       force_ssl: [hsts: true]
  #
  # Check `Plug.SSL` for all available options in `force_ssl`.

  # ## Configuring the mailer
  #
  # In production you need to configure the mailer to use a different adapter.
  # Here is an example configuration for Mailgun:
  #
  #     config :id_didi_sh, IdDidiSh.Mailer,
  #       adapter: Swoosh.Adapters.Mailgun,
  #       api_key: System.get_env("MAILGUN_API_KEY"),
  #       domain: System.get_env("MAILGUN_DOMAIN")
  #
  # Most non-SMTP adapters require an API client. Swoosh supports Req, Hackney,
  # and Finch out-of-the-box. This configuration is typically done at
  # compile-time in your config/prod.exs:
  #
  #     config :swoosh, :api_client, Swoosh.ApiClient.Req
  #
  # See https://swoosh.hexdocs.pm/Swoosh.html#module-installation for details.
end

if config_env() == :prod do
  # The deployed identity posture: .didi.sh cookie, Secure, env-injected
  # signing key (ID_SIGNING_JWK is validated at boot by IdDidiSh.Keys).
  #
  # cors_origins: the first consumer beyond didi.sh's own site/ —
  # augment.didi.sh (Build-Order Step 10, humain-vc unlock). Enumerated
  # explicitly per Plugs.CORS's own doc — the allowlist IS the trust
  # boundary statement, never a wildcard. Add each new *.didi.sh consumer
  # here as it goes live (decks, memos, …).
  config :id_didi_sh, :identity,
    issuer: System.get_env("ID_ISSUER") || "https://id.didi.sh",
    cookie_domain: System.get_env("ID_COOKIE_DOMAIN") || ".didi.sh",
    cookie_secure: true,
    cors_origins: ["https://augment.didi.sh"]
end

# Email — with RESEND_API_KEY present (Fly secret in prod; sourced .env for
# local testing), magic links go out via the Resend adapter. Without it,
# the per-env default stands (dev: Swoosh Local mailbox at /dev/mailbox).
# EMAIL_FROM overrides the sender — required to stay onboarding@resend.dev
# until the didi.sh domain is verified in Resend.
if resend_key = System.get_env("RESEND_API_KEY") do
  config :id_didi_sh, IdDidiSh.Mailer,
    adapter: IdDidiSh.Mailer.ResendAdapter,
    api_key: resend_key
end

if email_from = System.get_env("EMAIL_FROM") do
  config :id_didi_sh, :identity, email_from: email_from
end
