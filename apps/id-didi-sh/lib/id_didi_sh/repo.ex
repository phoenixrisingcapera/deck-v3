defmodule IdDidiSh.Repo do
  use Ecto.Repo,
    otp_app: :id_didi_sh,
    adapter: Ecto.Adapters.SQLite3
end
