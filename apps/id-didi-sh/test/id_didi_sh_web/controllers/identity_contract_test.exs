defmodule IdDidiShWeb.IdentityContractTest do
  @moduledoc """
  Group A — Identity contract.
  Registry: augment-it/context-v/specs/Corpora-Builder-Harmony-Test-Registry.md

  Pins the exact contract that augment-it's fake id-plane test fixture
  mimics. If this suite fails, the fake is lying and augment-it's tenancy
  tests are testing a fiction. Test names echo the registry's ✓-phrases.
  """
  use IdDidiShWeb.ConnCase, async: false

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token

  defp seed_user(email \\ "contract@example.com") do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: "Contract"})
    user
  end

  test "a signed-in session mints a JWT carrying only didi_id and session id", %{conn: _} do
    user = seed_user()
    session = Accounts.create_session(user)

    token = Token.sign(user.didi_id, session.id)
    %JOSE.JWT{fields: claims} = JOSE.JWT.peek_payload(token)

    assert claims["sub"] == user.didi_id
    assert claims["sid"] == session.id
    # Tenancy is NEVER baked into the token — org/role come from /api/me so
    # role changes propagate without waiting out a TTL. Assert the claim set
    # is exactly the minimal spine, nothing tenancy-shaped.
    assert MapSet.new(Map.keys(claims)) == MapSet.new(["sub", "sid", "iat", "exp", "iss"])
    refute Map.has_key?(claims, "org")
    refute Map.has_key?(claims, "memberships")
    refute Map.has_key?(claims, "role")
  end

  test "the JWKS endpoint serves the key that verifies a freshly minted JWT", %{conn: conn} do
    user = seed_user("jwks@example.com")
    session = Accounts.create_session(user)
    token = Token.sign(user.didi_id, session.id)

    %{"keys" => [key]} = conn |> get(~p"/.well-known/jwks.json") |> json_response(200)

    # Reconstruct the public key from ONLY what the endpoint published, and
    # prove it verifies a token this test minted — the real consumer round-trip.
    jwk = JOSE.JWK.from_map(key)
    assert {true, _payload, _jws} = JOSE.JWT.verify_strict(jwk, ["EdDSA"], token)
    # A tampered token must NOT verify against the same key.
    assert {false, _, _} = JOSE.JWT.verify_strict(jwk, ["EdDSA"], token <> "x")
  end

  test "/api/me returns org memberships for the session's didi_id", %{conn: _} do
    user = seed_user("member@example.com")
    {:ok, _} = Accounts.upsert_org("reach.edu", "Reach University")
    {:ok, _} = Accounts.upsert_membership(user.didi_id, "reach.edu", "editor")
    session = Accounts.create_session(user)
    token = Token.sign(user.didi_id, session.id)

    body =
      build_conn()
      |> put_req_cookie("didi_session", token)
      |> get(~p"/api/me")
      |> json_response(200)

    assert body["didi_id"] == user.didi_id
    assert %{"org_id" => "reach.edu", "role" => "editor"} in body["memberships"]
  end

  test "/api/session/refresh re-mints an expired JWT while the session row lives", %{conn: _} do
    user = seed_user("expired@example.com")
    session = Accounts.create_session(user)
    # Authentic signature, already past exp — the "zombie" cookie a live
    # session should heal invisibly.
    expired = Token.sign(user.didi_id, session.id, ttl_seconds: -10)
    assert {:error, :expired} = Token.verify(expired)

    conn =
      build_conn()
      |> put_req_cookie("didi_session", expired)
      |> post(~p"/api/session/refresh")

    assert %{"status" => "refreshed"} = json_response(conn, 200)
    # A fresh, now-valid cookie was set.
    reminted = conn.resp_cookies["didi_session"][:value]
    assert is_binary(reminted)
    assert {:ok, _claims} = Token.verify(reminted)
  end

  test "/api/session/refresh refuses when the session row is dead", %{conn: _} do
    user = seed_user("dead@example.com")
    session = Accounts.create_session(user)
    token = Token.sign(user.didi_id, session.id)
    # Revocation ends access — refresh is not a resurrection spell.
    Accounts.revoke_session(session.id)

    conn =
      build_conn()
      |> put_req_cookie("didi_session", token)
      |> post(~p"/api/session/refresh")

    assert %{"error" => "no live session"} = json_response(conn, 401)
  end
end
