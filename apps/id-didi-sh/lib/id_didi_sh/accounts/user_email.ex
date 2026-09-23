defmodule IdDidiSh.Accounts.UserEmail do
  use Ecto.Schema

  schema "user_emails" do
    field :didi_id, :string
    field :email, :string
    timestamps(type: :utc_datetime)
  end
end
