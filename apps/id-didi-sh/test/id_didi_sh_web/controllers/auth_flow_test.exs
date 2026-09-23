defmodule IdDidiShWeb.AuthFlowTest do
  use IdDidiShWeb.ConnCase, async: false

  alias IdDidiSh.Accounts

  defp seed_user(email \\ "flow@example.com") do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: "Flow"})
    user
  end

  defp cookie_from(conn) do
    conn.resp_cookies["didi_session"][:value]
  end

  test "the walking-skeleton loop: issue → redeem → me → refresh → logout", %{conn: conn} do
    user = seed_user()

    # issue — 202 regardless; grab the raw token from the context directly
    conn1 = post(conn, ~p"/api/magic-links", %{"email" => user.primary_email, "app" => "test"})
    assert conn1.status == 202
    {:ok, raw, _} = Accounts.issue_magic_link(user.primary_email)

    # redeem → cookie
    conn2 = post(build_conn(), ~p"/api/magic-links/redeem", %{"token" => raw})
    assert %{"didi_id" => didi_id} = json_response(conn2, 200)
    assert didi_id == user.didi_id
    token = cookie_from(conn2)
    assert is_binary(token)

    # me
    conn3 = build_conn() |> put_req_cookie("didi_session", token) |> get(~p"/api/me")
    assert %{"email" => email} = json_response(conn3, 200)
    assert email == user.primary_email

    # refresh re-mints
    conn4 =
      build_conn() |> put_req_cookie("didi_session", token) |> post(~p"/api/session/refresh")

    assert %{"status" => "refreshed"} = json_response(conn4, 200)

    # logout kills the session; me rejects even with the old (signed) token
    conn5 = build_conn() |> put_req_cookie("didi_session", token) |> delete(~p"/api/session")
    assert %{"status" => "signed_out"} = json_response(conn5, 200)

    conn6 = build_conn() |> put_req_cookie("didi_session", token) |> get(~p"/api/me")
    assert json_response(conn6, 401)
  end

  test "unknown email still gets 202 (no enumeration)", %{conn: conn} do
    conn = post(conn, ~p"/api/magic-links", %{"email" => "ghost@example.com"})
    assert conn.status == 202
    refute Map.has_key?(json_response(conn, 202), "dev_token")
  end

  test "jwks serves the Ed25519 public key", %{conn: conn} do
    conn = get(conn, ~p"/.well-known/jwks.json")
    assert %{"keys" => [key]} = json_response(conn, 200)
    assert key["kty"] == "OKP"
    assert key["crv"] == "Ed25519"
    assert key["alg"] == "EdDSA"
    refute Map.has_key?(key, "d")
  end

  test "the /access page: GET does not consume the token; POST redeems", %{conn: conn} do
    user = seed_user("clicker@example.com")
    {:ok, raw, _} = Accounts.issue_magic_link(user.primary_email)

    # Scanner prefetch: GET must leave the token alive
    conn1 = get(conn, ~p"/access?token=#{raw}")
    assert html_response(conn1, 200) =~ "Confirm your sign-in"

    # The human click: POST consumes it, sets the cookie
    conn2 = post(build_conn(), ~p"/access", %{"token" => raw})
    assert html_response(conn2, 200) =~ "Signed in"
    assert is_binary(conn2.resp_cookies["didi_session"][:value])

    # Reuse rejected with the error rendering
    conn3 = post(build_conn(), ~p"/access", %{"token" => raw})
    assert html_response(conn3, 200) =~ "invalid or expired"
  end

  test "/api/me without a cookie is 401", %{conn: conn} do
    assert conn |> get(~p"/api/me") |> json_response(401)
  end
end
