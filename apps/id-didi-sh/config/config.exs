# This file is responsible for configuring your application
# and its dependencies with the aid of the Config module.
#
# This configuration file is loaded before any dependency and
# is restricted to this project.

# General application configuration
import Config

config :id_didi_sh,
  ecto_repos: [IdDidiSh.Repo],
  generators: [timestamp_type: :utc_datetime]

# Configure the endpoint
config :id_didi_sh, IdDidiShWeb.Endpoint,
  url: [host: "localhost"],
  adapter: Bandit.PhoenixAdapter,
  render_errors: [
    formats: [html: IdDidiShWeb.ErrorHTML, json: IdDidiShWeb.ErrorJSON],
    layout: false
  ],
  pubsub_server: IdDidiSh.PubSub,
  live_view: [signing_salt: "Llq1G/Ch"]

# Configure LiveView
config :phoenix_live_view,
  # the attribute set on all root tags. Used for Phoenix.LiveView.ColocatedCSS.
  root_tag_attribute: "phx-r"

# Configure the mailer
#
# By default it uses the "Local" adapter which stores the emails
# locally. You can see the emails in your browser, at "/dev/mailbox".
#
# For production it's recommended to configure a different adapter
# at the `config/runtime.exs`.
config :id_didi_sh, IdDidiSh.Mailer, adapter: Swoosh.Adapters.Local

# Configure esbuild (the version is required)
config :esbuild,
  version: "0.25.4",
  id_didi_sh: [
    args:
      ~w(js/app.js --bundle --target=es2022 --outdir=../priv/static/assets/js --external:/fonts/* --external:/images/* --alias:@=.),
    cd: Path.expand("../assets", __DIR__),
    env: %{"NODE_PATH" => [Path.expand("../deps", __DIR__), Mix.Project.build_path()]}
  ]

# Configure tailwind (the version is required)
config :tailwind,
  version: "4.3.0",
  id_didi_sh: [
    args: ~w(
      --input=assets/css/app.css
      --output=priv/static/assets/css/app.css
    ),
    cd: Path.expand("..", __DIR__),
    env: %{"NODE_PATH" => [Path.expand("../deps", __DIR__), Mix.Project.build_path()]}
  ]

# Configure Elixir's Logger
config :logger, :default_formatter,
  format: "$time $metadata[$level] $message\n",
  metadata: [:request_id]

# Use Jason for JSON parsing in Phoenix
config :phoenix, :json_library, Jason

# Identity-service knobs. Per-env overrides in dev/test/runtime.
config :id_didi_sh, :identity,
  issuer: "https://id.didi.sh",
  cookie_name: "didi_session",
  cookie_domain: nil,
  cookie_secure: false,
  token_ttl_seconds: 12 * 60 * 60,
  session_ttl_days: 30,
  magic_link_ttl_minutes: 15,
  echo_login_tokens: false,
  allow_dev_keys: false

# Import environment specific config. This must remain at the bottom
# of this file so it overrides the configuration defined above.
import_config "#{config_env()}.exs"
