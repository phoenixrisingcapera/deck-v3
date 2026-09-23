defmodule IdDidiShWeb.PageControllerTest do
  use IdDidiShWeb.ConnCase

  describe "GET /" do
    test "renders the service datasheet, not the framework's welcome page", %{conn: conn} do
      html = conn |> get(~p"/") |> html_response(200)

      assert html =~ "id.didi.sh"
      assert html =~ "didi_session"
      assert html =~ "/.well-known/jwks.json"

      # The generator's landing page shipped for six weeks. If it ever comes
      # back, it comes back with its coral blobs and its framework tagline.
      refute html =~ "Peace of mind from prototype to production"
      refute html =~ "EE7868"
    end

    test "ships all three modes, dark by default" do
      html = build_conn() |> get(~p"/") |> html_response(200)

      # data-theme is what daisyUI reads; data-mode is what the credential
      # posture CSS reads. They are set together and must stay equal.
      assert html =~ ~s(data-theme="dark")
      assert html =~ ~s(data-mode="dark")

      for mode <- ~w(dark light vibrant) do
        assert html =~ ~s|setDidiMode('#{mode}')|,
               "expected a control for #{mode} mode"
      end
    end
  end
end
