defmodule IdDidiSh.CredentialsTest do
  use IdDidiSh.DataCase, async: false

  alias IdDidiSh.Accounts
  alias IdDidiSh.Credentials
  alias IdDidiSh.Repo

  @secret "sk-ant-supersecretvalue-9876"

  defp seed_user(email \\ "alice@example.com") do
    {:ok, user} = Accounts.create_user(%{primary_email: email, name: "Alice"})
    user
  end

  describe "create_credential/4" do
    test "stores a credential owned by a person, with a display hint" do
      user = seed_user()

      assert {:ok, c} =
               Credentials.create_credential(user.didi_id, "anthropic", "Alice personal", @secret)

      assert c.owner_didi_id == user.didi_id
      assert c.last_four == "9876"
      assert Credentials.live?(c)
    end

    test "rejects unknown provider, unknown user, empty value and missing label" do
      user = seed_user()

      assert {:error, :invalid_provider} =
               Credentials.create_credential(user.didi_id, "skynet", "L", @secret)

      assert {:error, :unknown_user} =
               Credentials.create_credential("nobody", "anthropic", "L", @secret)

      assert {:error, :empty_value} =
               Credentials.create_credential(user.didi_id, "anthropic", "L", "   ")

      assert {:error, :label_required} =
               Credentials.create_credential(user.didi_id, "anthropic", "", @secret)
    end

    test "short values are masked entirely rather than half-shown" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "other", "tiny", "abc123")
      assert c.last_four == "····"
    end
  end

  describe "encryption at rest — THE GATE" do
    test "the raw value is NOT stored in plaintext in the database" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "anthropic", "Alice", @secret)

      # Read the raw column, bypassing the Ecto type that would decrypt it.
      {:ok, %{rows: [[raw_column]]}} =
        Repo.query("SELECT value_encrypted FROM credentials WHERE id = ?1", [c.id])

      assert is_binary(raw_column)
      refute raw_column =~ @secret
      refute String.contains?(raw_column, "supersecret")
    end

    test "it round-trips through the vault" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "anthropic", "Alice", @secret)

      reloaded = Credentials.get_credential(c.id)
      assert reloaded.value_encrypted == @secret
    end
  end

  describe "render/1 — the only serializer" do
    test "cannot emit the value, and says so by omission" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "anthropic", "Alice", @secret)

      rendered = Credentials.render(c)

      refute Map.has_key?(rendered, :value_encrypted)
      refute rendered |> Jason.encode!() |> String.contains?(@secret)
      assert rendered.last_four == "9876"
    end

    test "a rendered list never contains the value either" do
      user = seed_user()
      {:ok, _} = Credentials.create_credential(user.didi_id, "anthropic", "one", @secret)
      {:ok, _} = Credentials.create_credential(user.didi_id, "openai", "two", "sk-openai-abcd1234")

      json =
        user.didi_id
        |> Credentials.list_credentials()
        |> Enum.map(&Credentials.render/1)
        |> Jason.encode!()

      refute String.contains?(json, @secret)
      refute String.contains?(json, "sk-openai-abcd1234")
    end
  end

  describe "revoke_credential/2" do
    test "the owner may revoke; the row survives for the usage record" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "anthropic", "Alice", @secret)

      assert {:ok, revoked} = Credentials.revoke_credential(c.id, user.didi_id)
      refute Credentials.live?(revoked)
      assert Credentials.get_credential(c.id), "revocation must not delete the row"
    end

    test "someone else may not revoke it — it is not their key" do
      alice = seed_user("alice@example.com")
      bob = seed_user("bob@example.com")
      {:ok, c} = Credentials.create_credential(alice.didi_id, "anthropic", "Alice", @secret)

      assert {:error, :not_the_owner} = Credentials.revoke_credential(c.id, bob.didi_id)
      assert Credentials.live?(Credentials.get_credential(c.id))
    end

    test "revoking twice is idempotent" do
      user = seed_user()
      {:ok, c} = Credentials.create_credential(user.didi_id, "anthropic", "Alice", @secret)
      {:ok, once} = Credentials.revoke_credential(c.id, user.didi_id)
      {:ok, twice} = Credentials.revoke_credential(c.id, user.didi_id)
      assert once.revoked_at == twice.revoked_at
    end
  end
end
