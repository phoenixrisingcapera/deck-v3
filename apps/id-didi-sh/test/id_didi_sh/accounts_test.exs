defmodule IdDidiSh.AccountsTest do
  use IdDidiSh.DataCase, async: false

  alias IdDidiSh.Accounts
  alias IdDidiSh.Token
  alias IdDidiSh.UUID7

  defp seed_user(email \\ "alice@example.com") do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: "Alice"})
    user
  end

  describe "UUID7" do
    test "generates valid, time-ordered v7 uuids" do
      a = UUID7.generate()
      b = UUID7.generate()
      assert a =~ ~r/^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
      assert a < b or binary_part(a, 0, 13) == binary_part(b, 0, 13)
    end
  end

  describe "magic links" do
    test "issue for unknown email is a silent noop (no enumeration)" do
      assert {:ok, :noop} = Accounts.issue_magic_link("nobody@example.com")
    end

    test "issue → redeem authenticates the existing user" do
      user = seed_user()
      assert {:ok, raw, _token} = Accounts.issue_magic_link(user.primary_email)
      assert {:ok, redeemed_user, _} = Accounts.redeem_magic_link(raw)
      assert redeemed_user.didi_id == user.didi_id
    end

    test "redeem is single-use" do
      user = seed_user()
      {:ok, raw, _} = Accounts.issue_magic_link(user.primary_email)
      assert {:ok, _, _} = Accounts.redeem_magic_link(raw)
      assert {:error, :invalid_token} = Accounts.redeem_magic_link(raw)
    end

    test "garbage tokens are rejected" do
      assert {:error, :invalid_token} = Accounts.redeem_magic_link("not-a-token")
    end

    test "email matching is case-insensitive" do
      seed_user("Bob@Example.com")
      assert {:ok, _raw, _} = Accounts.issue_magic_link("bob@example.com")
    end
  end

  describe "email aliases" do
    test "alias resolves to the same didi_id; magic link via alias authenticates it" do
      user = seed_user("primary@example.com")
      assert {:ok, "alt@humain.vc"} = Accounts.add_email_alias(user, "Alt@Humain.VC")
      assert Accounts.get_user_by_email("alt@humain.vc").didi_id == user.didi_id

      {:ok, raw, _} = Accounts.issue_magic_link("alt@humain.vc")
      assert {:ok, redeemed, _} = Accounts.redeem_magic_link(raw)
      assert redeemed.didi_id == user.didi_id
    end

    test "an address already in use (primary or alias) is rejected" do
      a = seed_user("a@example.com")
      b = seed_user("b@example.com")
      assert {:error, :taken} = Accounts.add_email_alias(a, "b@example.com")
      assert {:ok, _} = Accounts.add_email_alias(a, "shared@example.com")
      assert {:error, :taken} = Accounts.add_email_alias(b, "shared@example.com")
      assert {:error, :invalid_email} = Accounts.add_email_alias(a, "not-an-email")
    end
  end

  describe "orgs + memberships" do
    test "org upsert is idempotent by domain; membership upserts role" do
      assert {:ok, org} = Accounts.upsert_org("Humain.VC", "Humain VC")
      assert org.id == "humain.vc"
      assert {:ok, org2} = Accounts.upsert_org("humain.vc", "HUMAIN")
      assert org2.name == "HUMAIN"

      user = seed_user("founder@humain.vc")
      assert {:ok, m} = Accounts.upsert_membership(user.didi_id, "humain.vc", "org_owner")
      assert m.role == "org_owner"
      assert {:ok, m2} = Accounts.upsert_membership(user.didi_id, "humain.vc", "editor")
      assert m2.role == "editor"

      assert [%{org_id: "humain.vc", role: "editor"}] =
               Accounts.memberships_for(user.didi_id)
               |> Enum.map(&%{org_id: &1.org_id, role: &1.role})
    end

    test "membership rejects unknown role, user, org" do
      user = seed_user("someone@example.com")
      {:ok, _} = Accounts.upsert_org("example.com", "Example")

      assert {:error, :invalid_role} =
               Accounts.upsert_membership(user.didi_id, "example.com", "god")

      assert {:error, :unknown_user} = Accounts.upsert_membership("nope", "example.com", "editor")

      assert {:error, :unknown_org} =
               Accounts.upsert_membership(user.didi_id, "nowhere.io", "editor")
    end
  end

  describe "sessions + tokens" do
    test "create → live → revoke lifecycle" do
      user = seed_user()
      session = Accounts.create_session(user)
      assert Accounts.get_live_session(session.id)
      :ok = Accounts.revoke_session(session.id)
      refute Accounts.get_live_session(session.id)
    end

    test "signed token round-trips with the right claims" do
      user = seed_user()
      session = Accounts.create_session(user)
      jwt = Token.sign(user.didi_id, session.id)
      assert {:ok, claims} = Token.verify(jwt)
      assert claims.didi_id == user.didi_id
      assert claims.session_id == session.id
    end

    test "expired tokens are rejected as :expired" do
      user = seed_user()
      session = Accounts.create_session(user)
      jwt = Token.sign(user.didi_id, session.id, ttl_seconds: -1)
      assert {:error, :expired} = Token.verify(jwt)
    end

    test "tampered tokens fail signature verification" do
      user = seed_user()
      session = Accounts.create_session(user)
      jwt = Token.sign(user.didi_id, session.id)
      [h, p, _s] = String.split(jwt, ".")
      assert {:error, _} = Token.verify(h <> "." <> p <> ".AAAA")
    end
  end
end
