defmodule IdDidiShWeb.CredentialControllerTest do
  use IdDidiShWeb.ConnCase, async: false

  alias IdDidiSh.{Accounts, Entities}

  @secret "sk-ant-never-in-a-response-7777"

  defp user(email) do
    {:ok, u} = Accounts.create_user(%{primary_email: email, name: "Alice"})
    u
  end

  defp as(u) do
    {:ok, raw, _} = Accounts.issue_magic_link(u.primary_email)
    c = post(build_conn(), ~p"/api/magic-links/redeem", %{"token" => raw})
    build_conn() |> put_req_cookie("didi_session", c.resp_cookies["didi_session"][:value])
  end

  defp entity(slug) do
    {:ok, e} = Entities.create_entity(%{kind: "project", slug: slug, name: String.upcase(slug)})
    e
  end

  defp paste(u, label \\ "card") do
    post(as(u), ~p"/api/credentials", %{
      "provider" => "anthropic",
      "label" => label,
      "value" => @secret
    })
    |> json_response(201)
    |> Map.fetch!("credential")
  end

  describe "the gate — the value is in no response body" do
    test "not on create, not on list, not on usage" do
      alice = user("alice@example.com")
      apollo = entity("apollo")

      created = post(as(alice), ~p"/api/credentials", %{
        "provider" => "anthropic", "label" => "card", "value" => @secret
      })
      refute created |> response(201) |> String.contains?(@secret)
      assert json_response(created, 201)["credential"]["last_four"] == "7777"

      listed = get(as(alice), ~p"/api/credentials")
      refute listed |> response(200) |> String.contains?(@secret)

      cred_id = json_response(created, 201)["credential"]["id"]
      post(as(alice), ~p"/api/credentials/#{cred_id}/cascades", %{"entity_ids" => [apollo.id]})

      usage = get(as(alice), ~p"/api/credentials/#{cred_id}/usage")
      refute usage |> response(200) |> String.contains?(@secret)
    end
  end

  describe "lending through the API" do
    test "one act, three entities, and the notice says who it reaches" do
      alice = user("alice@example.com")
      cred = paste(alice)
      ids = Enum.map(["apollo", "boreas", "cronus"], &entity(&1).id)

      conn =
        post(as(alice), ~p"/api/credentials/#{cred["id"]}/cascades", %{"entity_ids" => ids})

      body = json_response(conn, 201)
      assert length(body["loans"]) == 3
      assert body["notice"] =~ "including anyone added later"

      # Derived admin, with no membership rows.
      for id <- ids, do: assert(Entities.effective_role(id, alice.didi_id) == :admin)
    end

    test "pulling the cascade takes it back everywhere; pulling one loan does not" do
      alice = user("alice@example.com")
      cred = paste(alice)
      a = entity("apollo")
      b = entity("boreas")

      cascade =
        post(as(alice), ~p"/api/credentials/#{cred["id"]}/cascades", %{
          "entity_ids" => [a.id, b.id]
        })
        |> json_response(201)
        |> get_in(["cascade", "id"])

      # Partial withdrawal first.
      assert delete(as(alice), ~p"/api/cascades/#{cascade}/loans/#{a.id}") |> json_response(200)
      assert Entities.effective_role(a.id, alice.didi_id) == nil
      assert Entities.effective_role(b.id, alice.didi_id) == :admin

      # Then the whole thing.
      assert delete(as(alice), ~p"/api/cascades/#{cascade}") |> json_response(200)
      assert Entities.effective_role(b.id, alice.didi_id) == nil
    end

    test "someone else cannot pull my cascade" do
      alice = user("alice@example.com")
      bob = user("bob@example.com")
      cred = paste(alice)
      a = entity("apollo")

      cascade =
        post(as(alice), ~p"/api/credentials/#{cred["id"]}/cascades", %{"entity_ids" => [a.id]})
        |> json_response(201)
        |> get_in(["cascade", "id"])

      assert delete(as(bob), ~p"/api/cascades/#{cascade}") |> json_response(403)
    end
  end

  describe "the meter" do
    test "shows per-entity spend to the owner" do
      alice = user("alice@example.com")
      cred = paste(alice)
      a = entity("apollo")

      post(as(alice), ~p"/api/credentials/#{cred["id"]}/cascades", %{"entity_ids" => [a.id]})

      {:ok, _} = Accounts.upsert_app("augment-it", "Augment It")
      {:ok, token, _} = Accounts.issue_app_token("augment-it")

      build_conn()
      |> put_req_header("authorization", "Bearer #{token}")
      |> post(~p"/api/internal/resolve", %{
        "entity_id" => a.id,
        "provider" => "anthropic",
        "cost_estimate" => 250
      })

      body = get(as(alice), ~p"/api/credentials/#{cred["id"]}/usage") |> json_response(200)
      assert [row] = body["by_entity"]
      assert row["entity_id"] == a.id
      assert row["cost_estimate"] == 250
    end

    test "is owner-only — not even an entity admin may read it" do
      alice = user("alice@example.com")
      bob = user("bob@example.com")
      cred = paste(alice)
      a = entity("apollo")
      {:ok, _} = Entities.add_member(a.id, bob.didi_id, "org_admin")

      post(as(alice), ~p"/api/credentials/#{cred["id"]}/cascades", %{"entity_ids" => [a.id]})

      conn = get(as(bob), ~p"/api/credentials/#{cred["id"]}/usage")
      assert json_response(conn, 403)["error"] == "not_the_owner"
    end
  end

  describe "revocation" do
    test "the owner revokes; someone else cannot" do
      alice = user("alice@example.com")
      bob = user("bob@example.com")
      cred = paste(alice)

      assert delete(as(bob), ~p"/api/credentials/#{cred["id"]}") |> json_response(403)
      assert delete(as(alice), ~p"/api/credentials/#{cred["id"]}") |> json_response(200)
    end
  end
end
