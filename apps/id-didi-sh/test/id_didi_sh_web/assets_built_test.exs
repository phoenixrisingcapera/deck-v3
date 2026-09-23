defmodule IdDidiShWeb.AssetsBuiltTest do
  use ExUnit.Case, async: true

  @moduledoc """
  A smoke test for a class of failure the rest of the suite cannot see.

  LiveViewTest drives the server directly — no browser, no JavaScript, no
  bundle. So every LiveView test can pass while the page is inert in a real
  browser, which is exactly what happened on 2026-08-21: `mix assets.build` had
  been failing since the walking skeleton, `app.js` was never emitted, and
  `/keys` rendered once and then ignored every click.

  This does not replace a browser drive. It catches the cheapest version of the
  problem at the cost of two assertions.
  """

  @app_js Path.join([:code.priv_dir(:id_didi_sh), "static", "assets", "js", "app.js"])
  @app_css Path.join([:code.priv_dir(:id_didi_sh), "static", "assets", "css", "app.css"])

  test "the JavaScript bundle exists — without it, every LiveView is a photograph" do
    assert File.exists?(@app_js),
           "priv/static/assets/js/app.js is missing. Run `mix assets.build`. " <>
             "LiveView needs this to connect; without it the page renders once and dies."

    assert File.stat!(@app_js).size > 10_000,
           "app.js exists but is suspiciously small — did the build half-fail?"
  end

  test "the stylesheet exists" do
    assert File.exists?(@app_css), "priv/static/assets/css/app.css is missing. Run `mix assets.build`."
  end
end
