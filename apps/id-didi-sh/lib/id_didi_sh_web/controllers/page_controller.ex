defmodule IdDidiShWeb.PageController do
  use IdDidiShWeb, :controller

  def home(conn, _params) do
    render(conn, :home)
  end
end
