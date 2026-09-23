defmodule IdDidiShWeb.ThemeTokensTest do
  use ExUnit.Case, async: true

  @web_dir "lib/id_didi_sh_web"

  # Tailwind's built-in palette is theme-blind: bg-gray-50 is near-white in
  # every mode. Paired with base-content (near-white in dark) it renders
  # white-on-white — which is exactly how the lend panel shipped, invisible
  # until someone looked at it.
  #
  # Semantic tokens rebind per mode; the raw palette does not. So the raw
  # palette is banned from the web layer.
  @banned ~w(gray slate zinc stone red orange amber yellow lime green emerald
             teal cyan sky blue indigo violet purple fuchsia pink rose
             black white)

  test "no theme-blind Tailwind palette classes in the web layer" do
    pattern =
      ~r/\b(?:bg|text|border|from|via|to|ring|divide|outline|decoration|shadow)-(?:#{Enum.join(@banned, "|")})(?:-\d{2,3})?\b/

    offenders =
      Path.wildcard("#{@web_dir}/**/*.{ex,heex}")
      |> Enum.flat_map(fn path ->
        path
        |> File.read!()
        |> String.split("\n")
        |> Enum.with_index(1)
        |> Enum.filter(fn {line, _} -> Regex.match?(pattern, line) end)
        |> Enum.map(fn {line, n} -> "#{path}:#{n}  #{String.trim(line)}" end)
      end)

    assert offenders == [],
           """
           Theme-blind colour classes found. Use semantic tokens instead —
           they rebind across dark / light / vibrant, the raw palette does not.

             bg-gray-50   -> bg-base-200 / bg-base-300
             bg-black     -> btn btn-primary, or bg-primary text-primary-content
             text-red-600 -> text-error
             bg-amber-50  -> bg-warning/10 border-warning/40

           #{Enum.join(offenders, "\n")}
           """
  end
end
