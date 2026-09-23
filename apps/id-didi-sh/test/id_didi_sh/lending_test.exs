defmodule IdDidiSh.LendingTest do
  use IdDidiSh.DataCase, async: false

  alias IdDidiSh.{Accounts, Credentials, Entities}

  @secret "sk-ant-lendingtest-4321"

  defp user(email), do: (fn -> {:ok, u} = Accounts.create_user(%{primary_email: email, name: String.capitalize(hd(String.split(email, "@")))}); u end).()

  defp entity(slug), do: (fn -> {:ok, e} = Entities.create_entity(%{kind: "project", slug: slug, name: String.upcase(slug)}); e end).()

  defp credential(owner), do: (fn -> {:ok, c} = Credentials.create_credential(owner.didi_id, "anthropic", "card", @secret); c end).()

  describe "lend/4 — the cascade — THE GATE" do
    test "one act, three entities: one cascade, three loans, admin in all three" do
      alice = user("alice@example.com")
      cred = credential(alice)
      [a, b, c] = [entity("apollo"), entity("boreas"), entity("cronus")]

      assert {:ok, cascade, loans} =
               Credentials.lend(cred.id, [a.id, b.id, c.id], %{}, alice.didi_id)

      assert length(loans) == 3
      assert Enum.all?(loans, &(&1.cascade_id == cascade.id))

      # Admin everywhere — WITHOUT a membership row anywhere.
      for e <- [a, b, c] do
        assert Entities.effective_role(e.id, alice.didi_id) == :admin
        refute Entities.get_membership(e.id, alice.didi_id)
      end
    end

    test "ending the cascade removes admin everywhere at once" do
      alice = user("alice@example.com")
      cred = credential(alice)
      [a, b] = [entity("apollo"), entity("boreas")]
      {:ok, cascade, _} = Credentials.lend(cred.id, [a.id, b.id], %{}, alice.didi_id)

      assert {:ok, _} = Credentials.end_cascade(cascade.id, alice.didi_id)

      assert Entities.effective_role(a.id, alice.didi_id) == nil
      assert Entities.effective_role(b.id, alice.didi_id) == nil
    end

    test "ending ONE loan leaves the rest of the cascade live" do
      alice = user("alice@example.com")
      cred = credential(alice)
      [a, b] = [entity("apollo"), entity("boreas")]
      {:ok, cascade, _} = Credentials.lend(cred.id, [a.id, b.id], %{}, alice.didi_id)

      assert :ok = Credentials.end_loan(cascade.id, a.id, alice.didi_id)

      assert Entities.effective_role(a.id, alice.didi_id) == nil
      assert Entities.effective_role(b.id, alice.didi_id) == :admin
    end
  end

  describe "who may lend and un-lend" do
    test "you cannot lend a key that is not yours" do
      alice = user("alice@example.com")
      bob = user("bob@example.com")
      cred = credential(alice)
      a = entity("apollo")

      assert {:error, :not_the_owner} = Credentials.lend(cred.id, [a.id], %{}, bob.didi_id)
    end

    test "only the lender may end the cascade or a loan" do
      alice = user("alice@example.com")
      bob = user("bob@example.com")
      cred = credential(alice)
      a = entity("apollo")
      {:ok, cascade, _} = Credentials.lend(cred.id, [a.id], %{}, alice.didi_id)

      assert {:error, :not_the_lender} = Credentials.end_cascade(cascade.id, bob.didi_id)
      assert {:error, :not_the_lender} = Credentials.end_loan(cascade.id, a.id, bob.didi_id)
    end

    test "rejects empty targets, unknown entity, revoked credential and bad period" do
      alice = user("alice@example.com")
      cred = credential(alice)
      a = entity("apollo")

      assert {:error, :no_entities} = Credentials.lend(cred.id, [], %{}, alice.didi_id)
      assert {:error, :unknown_entity} = Credentials.lend(cred.id, ["nope"], %{}, alice.didi_id)

      assert {:error, :invalid_cap_period} =
               Credentials.lend(cred.id, [a.id], %{cap_period: "fortnight"}, alice.didi_id)

      {:ok, _} = Credentials.revoke_credential(cred.id, alice.didi_id)
      assert {:error, :credential_revoked} = Credentials.lend(cred.id, [a.id], %{}, alice.didi_id)
    end
  end

  describe "a loan dies with its credential" do
    test "revoking the credential ends access without touching the loan rows" do
      alice = user("alice@example.com")
      cred = credential(alice)
      a = entity("apollo")
      {:ok, _cascade, _} = Credentials.lend(cred.id, [a.id], %{}, alice.didi_id)

      assert Entities.effective_role(a.id, alice.didi_id) == :admin
      {:ok, _} = Credentials.revoke_credential(cred.id, alice.didi_id)
      assert Entities.effective_role(a.id, alice.didi_id) == nil
    end

    test "an expired cascade confers nothing" do
      alice = user("alice@example.com")
      cred = credential(alice)
      a = entity("apollo")
      past = DateTime.utc_now() |> DateTime.add(-3600) |> DateTime.truncate(:second)

      {:ok, _cascade, _} = Credentials.lend(cred.id, [a.id], %{expires_at: past}, alice.didi_id)

      assert Entities.effective_role(a.id, alice.didi_id) == nil
    end
  end

  describe "lenders count as access (closes the under-reporting issue)" do
    test "a lender with no membership appears in list_entities_for" do
      alice = user("alice@example.com")
      cred = credential(alice)
      a = entity("apollo")
      {:ok, _, _} = Credentials.lend(cred.id, [a.id], %{}, alice.didi_id)

      slugs = alice.didi_id |> Entities.list_entities_for() |> Enum.map(& &1.slug)
      assert "apollo" in slugs
    end

    test "the removal disclosure counts entities they only lend to" do
      bob = user("bob@example.com")
      acme = entity("acme")
      apollo = entity("apollo")

      # Bob is a member of acme, and lends to apollo without being a member.
      {:ok, _} = Entities.add_member(acme.id, bob.didi_id, "editor")
      bob_cred = credential(bob)
      {:ok, _, _} = Credentials.lend(bob_cred.id, [apollo.id], %{}, bob.didi_id)

      survivors = Entities.also_member_of(bob.didi_id, acme.id) |> Enum.map(& &1.slug)

      assert "apollo" in survivors,
             "removing Bob from acme must disclose that he still reaches apollo by lending"
    end
  end
end
