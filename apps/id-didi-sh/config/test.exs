import Config

# Configure your database
#
# The MIX_TEST_PARTITION environment variable can be used
# to provide built-in test partitioning in CI environment.
# Run `mix help test` for more information.
config :id_didi_sh, IdDidiSh.Repo,
  database: Path.expand("../id_didi_sh_test.db", __DIR__),
  pool_size: 5,
  pool: Ecto.Adapters.SQL.Sandbox

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :id_didi_sh, IdDidiShWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "/Lc0raDn3yOZfvPrnfGtetD/0Xn7bzUr7yxZvz1cI+pNAIiu4gm23eOpuuaT52Wo",
  server: false

# In test we don't send emails
config :id_didi_sh, IdDidiSh.Mailer, adapter: Swoosh.Adapters.Test

# Disable swoosh api client as it is only required for production adapters
config :swoosh, :api_client, false

# Print only warnings and errors during test
config :logger, level: :warning

# Initialize plugs at runtime for faster test compilation
config :phoenix, :plug_init_mode, :runtime

# Enable helpful, but potentially expensive runtime checks
config :phoenix_live_view,
  enable_expensive_runtime_checks: true

# Sort query params output of verified routes for robust url comparisons
config :phoenix,
  sort_verified_routes_query_params: true

config :id_didi_sh, :identity,
  issuer: "http://localhost:4002",
  allow_dev_keys: true
