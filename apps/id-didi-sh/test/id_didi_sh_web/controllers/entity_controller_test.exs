defmodule IdDidiShWeb.EntityControllerTest do
  use IdDidiShWeb.ConnCase, async: false

  alias IdDidiSh.Accounts
  alias IdDidiSh.Entities

  defp seed_user(email, name) do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: name})
    user
  end

  # Mint a real session the same way the auth flow does, so these tests
  # exercise the actual RequireUser plug rather than a stubbed assign.
  defp sign_in(user) do
    {:ok, raw, _} = Accounts.issue_magic_link(user.primary_email)
    conn = post(build_conn(), ~p"/api/magic-links/redeem", %{"token" => raw})
    conn.resp_cookies["didi_session"][:value]
  end

  defp as(user) do
    build_conn() |> put_req_cookie("didi_session", sign_in(user))
  end

  defp create_entity(user, kind, slug, name) do
    conn = post(as(user), ~p"/api/entities", %{"kind" => kind, "slug" => slug, "name" => name})
    json_response(conn, 201)["entity"]
  end

  describe "authentication" do
    test "rejects an unauthenticated request" do
      conn = get(build_conn(), ~p"/api/entities")
      assert json_response(conn, 401)["error"] == "unauthenticated"
    end
  end

  describe "create and read" do
    test "creating an entity makes the creator an owner" do
      alice = seed_user("alice@example.com", "Alice")
      entity = create_entity(alice, "project", "apollo", "Apollo")

      conn = get(as(alice), ~p"/api/entities/#{entity["id"]}")
      body = json_response(conn, 200)
      assert body["entity"]["slug"] == "apollo"
      assert body["effective_role"] == "org_owner"
    end

    test "a non-member cannot read the entity" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      entity = create_entity(alice, "project", "apollo", "Apollo")

      conn = get(as(bob), ~p"/api/entities/#{entity["id"]}")
      assert json_response(conn, 403)["error"] == "not_a_member"
    end

    test "index lists only my entities" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      create_entity(alice, "project", "apollo", "Apollo")
      create_entity(bob, "project", "gemini", "Gemini")

      slugs = get(as(alice), ~p"/api/entities") |> json_response(200) |> Map.fetch!("entities")
      assert Enum.map(slugs, & &1["slug"]) == ["apollo"]
    end
  end

  describe "members" do
    test "an admin adds an existing user" do
      alice = seed_user("alice@example.com", "Alice")
      _bob = seed_user("bob@example.com", "Bob")
      entity = create_entity(alice, "project", "apollo", "Apollo")

      conn =
        post(as(alice), ~p"/api/entities/#{entity["id"]}/members", %{
          "email" => "bob@example.com",
          "role" => "editor"
        })

      assert json_response(conn, 201)["member"]["role"] == "editor"
    end

    test "a non-admin member cannot add" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      entity = create_entity(alice, "project", "apollo", "Apollo")
      {:ok, _} = Entities.add_member(entity["id"], bob.didi_id, "viewer")

      conn =
        post(as(bob), ~p"/api/entities/#{entity["id"]}/members", %{
          "email" => "alice@example.com",
          "role" => "editor"
        })

      assert json_response(conn, 403)["error"] == "not_an_admin"
    end

    test "adding an unknown email invites them (202), rather than adding a member" do
      alice = seed_user("alice@example.com", "Alice")
      entity = create_entity(alice, "project", "apollo", "Apollo")

      conn =
        post(as(alice), ~p"/api/entities/#{entity["id"]}/members", %{
          "email" => "nobody@example.com",
          "role" => "editor"
        })

      # 202, not 201: the invite is out, but they are not a member until they
      # redeem it. Full round-trip lives in InviteFlowTest.
      assert json_response(conn, 202)["invited"]["email"] == "nobody@example.com"
    end
  end

  describe "the removal disclosure (Ruling 1b) — THE GATE" do
    test "DELETE member returns also_member_of and a disclosure sentence" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")

      acme = create_entity(alice, "organization", "acme", "Acme Corp")
      apollo = create_entity(alice, "project", "apollo", "Apollo")
      q3 = create_entity(alice, "workspace", "q3", "Q3 Diligence")

      for e <- [acme, apollo, q3] do
        {:ok, _} = Entities.add_member(e["id"], bob.didi_id, "editor")
      end

      conn = delete(as(alice), ~p"/api/entities/#{acme["id"]}/members/#{bob.didi_id}")
      body = json_response(conn, 200)

      names = body["also_member_of"] |> Enum.map(& &1["name"]) |> Enum.sort()
      assert names == ["Apollo", "Q3 Diligence"]
      assert body["disclosure"] =~ "Bob will keep access to:"
      assert body["disclosure"] =~ "Apollo"
    end

    test "removal does not cascade — the other memberships survive in the DB" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")

      acme = create_entity(alice, "organization", "acme", "Acme Corp")
      apollo = create_entity(alice, "project", "apollo", "Apollo")

      for e <- [acme, apollo] do
        {:ok, _} = Entities.add_member(e["id"], bob.didi_id, "editor")
      end

      delete(as(alice), ~p"/api/entities/#{acme["id"]}/members/#{bob.didi_id}")

      assert Entities.effective_role(acme["id"], bob.didi_id) == nil
      assert Entities.effective_role(apollo["id"], bob.didi_id) == "editor"
    end

    test "with nothing left, the disclosure says so plainly" do
      alice = seed_user("alice@example.com", "Alice")
      bob = seed_user("bob@example.com", "Bob")
      apollo = create_entity(alice, "project", "apollo", "Apollo")
      {:ok, _} = Entities.add_member(apollo["id"], bob.didi_id, "editor")

      conn = delete(as(alice), ~p"/api/entities/#{apollo["id"]}/members/#{bob.didi_id}")
      body = json_response(conn, 200)

      assert body["also_member_of"] == []
      assert body["disclosure"] =~ "no longer have access to anything here"
    end
  end
end
