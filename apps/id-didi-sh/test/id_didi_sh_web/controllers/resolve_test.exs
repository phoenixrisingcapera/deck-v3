defmodule IdDidiShWeb.ResolveTest do
  use IdDidiShWeb.ConnCase, async: false

  alias IdDidiSh.{Accounts, Credentials, Entities}

  @secret "sk-ant-resolve-me-5555"

  defp user(email) do
    {:ok, u} = Accounts.create_user(%{primary_email: email, name: "Alice"})
    u
  end

  defp entity(slug) do
    {:ok, e} = Entities.create_entity(%{kind: "project", slug: slug, name: String.upcase(slug)})
    e
  end

  defp lent_setup do
    alice = user("alice@example.com")
    apollo = entity("apollo")
    {:ok, cred} = Credentials.create_credential(alice.didi_id, "anthropic", "card", @secret)
    {:ok, cascade, _} = Credentials.lend(cred.id, [apollo.id], %{}, alice.didi_id)
    {:ok, _} = Accounts.upsert_app("augment-it", "Augment It")
    {:ok, raw, _app} = Accounts.issue_app_token("augment-it")
    %{alice: alice, apollo: apollo, cred: cred, cascade: cascade, app_token: raw}
  end

  defp as_app(token) do
    build_conn() |> put_req_header("authorization", "Bearer #{token}")
  end

  describe "the gate — a registered app resolves and usage is recorded" do
    test "returns the value and writes a usage row with the right entity" do
      ctx = lent_setup()

      conn =
        post(as_app(ctx.app_token), ~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic",
          "cost_estimate" => 42
        })

      assert json_response(conn, 200)["value"] == @secret

      [row] = Credentials.usage_for_credential(ctx.cred.id)
      assert row.entity_id == ctx.apollo.id
      assert row.calls == 1
      assert row.cost_estimate == 42
    end
  end

  describe "a browser must never reach this" do
    test "a request carrying a user session is REJECTED, not merely ignored" do
      ctx = lent_setup()

      {:ok, raw, _} = Accounts.issue_magic_link("alice@example.com")
      signed_in = post(build_conn(), ~p"/api/magic-links/redeem", %{"token" => raw})
      cookie = signed_in.resp_cookies["didi_session"][:value]

      conn =
        build_conn()
        |> put_req_cookie("didi_session", cookie)
        |> put_req_header("authorization", "Bearer #{ctx.app_token}")
        |> post(~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic"
        })

      assert json_response(conn, 403)["error"] == "app_credential_required"
    end

    test "no credential at all is refused" do
      ctx = lent_setup()

      conn =
        post(build_conn(), ~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic"
        })

      assert json_response(conn, 401)["error"] == "app_credential_required"
    end

    test "a bad app token is refused" do
      ctx = lent_setup()

      conn =
        post(as_app("not-a-real-token"), ~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic"
        })

      assert json_response(conn, 401)["error"] == "invalid_app_credential"
    end
  end

  describe "nothing lent" do
    test "says so, and tells a human what to do" do
      ctx = lent_setup()
      other = entity("boreas")

      conn =
        post(as_app(ctx.app_token), ~p"/api/internal/resolve", %{
          "entity_id" => other.id,
          "provider" => "anthropic"
        })

      body = json_response(conn, 404)
      assert body["error"] == "no_live_loan"
      assert body["detail"] =~ "Ask someone to lend one"
    end

    test "a withdrawn cascade stops resolving immediately" do
      ctx = lent_setup()
      {:ok, _} = Credentials.end_cascade(ctx.cascade.id, ctx.alice.didi_id)

      conn =
        post(as_app(ctx.app_token), ~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic"
        })

      assert json_response(conn, 404)["error"] == "no_live_loan"
    end
  end

  describe "the cap" do
    test "refuses once the lender's cap is reached" do
      alice = user("alice@example.com")
      apollo = entity("apollo")
      {:ok, cred} = Credentials.create_credential(alice.didi_id, "anthropic", "card", @secret)

      {:ok, _cascade, _} =
        Credentials.lend(cred.id, [apollo.id], %{spend_cap: 100, cap_period: "month"}, alice.didi_id)

      {:ok, _} = Accounts.upsert_app("augment-it", "Augment It")
      {:ok, token, _} = Accounts.issue_app_token("augment-it")

      # Spend up to the cap.
      conn1 =
        post(as_app(token), ~p"/api/internal/resolve", %{
          "entity_id" => apollo.id,
          "provider" => "anthropic",
          "cost_estimate" => 100
        })

      assert json_response(conn1, 200)["value"] == @secret

      conn2 =
        post(as_app(token), ~p"/api/internal/resolve", %{
          "entity_id" => apollo.id,
          "provider" => "anthropic",
          "cost_estimate" => 1
        })

      assert json_response(conn2, 402)["error"] == "cap_exceeded"
    end
  end

  describe "a disabled app" do
    test "is refused even with a valid token" do
      ctx = lent_setup()
      app = Accounts.get_app("augment-it")
      {:ok, _} = app |> Ecto.Changeset.change(enabled: false) |> IdDidiSh.Repo.update()

      conn =
        post(as_app(ctx.app_token), ~p"/api/internal/resolve", %{
          "entity_id" => ctx.apollo.id,
          "provider" => "anthropic"
        })

      assert json_response(conn, 403)["error"] == "app_disabled"
    end
  end
end
