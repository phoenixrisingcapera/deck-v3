defmodule IdDidiSh.UUID7 do
  @moduledoc """
  UUIDv7 generation (RFC 9562): 48-bit unix-ms timestamp + version/variant
  bits + 74 bits of randomness. Time-ordered, so `didi_id`s sort by mint
  time — the property the spec wants from the stable person id.

  Hand-rolled (~20 lines) rather than a dependency; verified by tests.
  """

  @spec generate() :: String.t()
  def generate do
    unix_ms = System.system_time(:millisecond)
    <<rand_a::12, rand_b::62, _::6>> = :crypto.strong_rand_bytes(10)

    <<u0::32, u1::16, u2::16, u3::16, u4::48>> =
      <<unix_ms::48, 7::4, rand_a::12, 2::2, rand_b::62>>

    :io_lib.format("~8.16.0b-~4.16.0b-~4.16.0b-~4.16.0b-~12.16.0b", [u0, u1, u2, u3, u4])
    |> IO.iodata_to_binary()
  end
end
