defmodule IdDidiShWeb.JWKSController do
  use IdDidiShWeb, :controller

  @doc """
  GET /.well-known/jwks.json — the public key set consumers verify with.
  Cacheable; consumers should honor Cache-Control and re-fetch on unknown
  `kid` (the rotation contract).
  """
  def show(conn, _params) do
    conn
    |> put_resp_header("cache-control", "public, max-age=300")
    |> json(IdDidiSh.Keys.jwks())
  end
end
