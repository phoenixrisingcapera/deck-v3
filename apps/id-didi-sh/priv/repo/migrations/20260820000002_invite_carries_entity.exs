defmodule IdDidiSh.Repo.Migrations.InviteCarriesEntity do
  use Ecto.Migration

  # login_tokens already carries org_id + role for org invites. Entities need
  # the same, so redeeming an invite can attach the membership it was issued
  # for. Same table, same single-use + TTL discipline — an entity invite is a
  # magic link with a destination, not a new mechanism.
  def change do
    alter table(:login_tokens) do
      add :entity_id, :string
    end
  end
end
