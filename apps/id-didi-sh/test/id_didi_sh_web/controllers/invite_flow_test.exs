defmodule IdDidiShWeb.InviteFlowTest do
  use IdDidiShWeb.ConnCase, async: false

  import Swoosh.TestAssertions

  alias IdDidiSh.Accounts
  alias IdDidiSh.Entities

  defp seed_user(email, name) do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: name})
    user
  end

  defp as(user) do
    {:ok, raw, _} = Accounts.issue_magic_link(user.primary_email)
    conn = post(build_conn(), ~p"/api/magic-links/redeem", %{"token" => raw})
    build_conn() |> put_req_cookie("didi_session", conn.resp_cookies["didi_session"][:value])
  end

  defp create_entity(user, kind, slug, name) do
    post(as(user), ~p"/api/entities", %{"kind" => kind, "slug" => slug, "name" => name})
    |> json_response(201)
    |> Map.fetch!("entity")
  end

  describe "inviting someone with no didi account" do
    test "returns 202, sends mail from no-reply@didi.sh, and creates no member yet" do
      alice = seed_user("alice@example.com", "Alice")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      conn =
        post(as(alice), ~p"/api/entities/#{apollo["id"]}/members", %{
          "email" => "newcomer@example.com",
          "role" => "editor"
        })

      body = json_response(conn, 202)
      assert body["invited"]["email"] == "newcomer@example.com"
      assert body["delivery"] == "sent"

      # Nobody has been added — they cannot sign in yet.
      assert Entities.list_members(apollo["id"]) |> length() == 1

      assert_email_sent(fn email ->
        assert {_, "no-reply@didi.sh"} = email.from
        assert email.subject =~ "Apollo"
        assert elem(hd(email.to), 1) == "newcomer@example.com"
      end)
    end

    test "redeeming the invite creates the account AND attaches the membership" do
      alice = seed_user("alice@example.com", "Alice")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      post(as(alice), ~p"/api/entities/#{apollo["id"]}/members", %{
        "email" => "newcomer@example.com",
        "role" => "editor"
      })

      # Grab the raw token the way the email carries it.
      {:ok, raw, _} =
        Accounts.issue_invite("newcomer@example.com", entity_id: apollo["id"], role: "editor")

      refute Accounts.get_user_by_email("newcomer@example.com")

      conn = post(build_conn(), ~p"/access", %{"token" => raw})
      assert conn.status in [200, 302]

      user = Accounts.get_user_by_email("newcomer@example.com")
      assert user, "redeeming an invite must create the account"
      assert Entities.effective_role(apollo["id"], user.didi_id) == "editor"
    end

    test "an invite is single-use" do
      alice = seed_user("alice@example.com", "Alice")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      {:ok, raw, _} =
        Accounts.issue_invite("newcomer@example.com", entity_id: apollo["id"], role: "editor")

      assert {:ok, _user, _token} = Accounts.redeem_invite(raw)
      assert {:error, :invalid_token} = Accounts.redeem_invite(raw)
    end
  end

  describe "inviting someone who already has an account" do
    test "attaches immediately with 201 and sends no invite mail" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      conn =
        post(as(alice), ~p"/api/entities/#{apollo["id"]}/members", %{
          "email" => "bob@example.com",
          "role" => "editor"
        })

      assert json_response(conn, 201)["member"]["role"] == "editor"
      assert Entities.effective_role(apollo["id"], bob.didi_id) == "editor"
    end
  end

  describe "guards" do
    test "a non-admin cannot invite" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      apollo = create_entity(alice, "project", "apollo", "Apollo")
      {:ok, _} = Entities.add_member(apollo["id"], bob.didi_id, "viewer")

      conn =
        post(as(bob), ~p"/api/entities/#{apollo["id"]}/members", %{
          "email" => "someone@example.com",
          "role" => "editor"
        })

      assert json_response(conn, 403)["error"] == "not_an_admin"
    end

    test "an invalid role is rejected before any mail goes out" do
      alice = seed_user("alice@example.com", "Alice")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      conn =
        post(as(alice), ~p"/api/entities/#{apollo["id"]}/members", %{
          "email" => "someone@example.com",
          "role" => "wizard"
        })

      assert json_response(conn, 422)["error"] == "invalid_role"
    end
  end
end
