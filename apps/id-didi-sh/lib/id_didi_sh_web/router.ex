defmodule IdDidiShWeb.Router do
  use IdDidiShWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {IdDidiShWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :api do
    plug :accepts, ["json"]
  end

  # Authenticated JSON: verifies the didi_session cookie AND the session row.
  pipeline :api_authed do
    plug :accepts, ["json"]
    plug IdDidiShWeb.Plugs.RequireUser
  end

  scope "/", IdDidiShWeb do
    pipe_through :browser

    get "/", PageController, :home
    # The magic-link landing (emails point here). Two-step on purpose:
    # GET renders a confirm button; only the POST consumes the token —
    # mail-scanner prefetch can't burn a single-use link.
    get "/access", AccessController, :show
    post "/access", AccessController, :redeem

    # The hosted front door. didi.sh and the splash both advertise "one login"
    # and had nowhere to send anyone — a call-to-action with no destination is
    # worse than none. Apps with their own login screen still call
    # `POST /api/magic-links` directly and never link here.
    get "/auth", AuthController, :new
    post "/auth", AuthController, :create

    # What the credential resolves to: identity, entities, keys. Signing in used
    # to end at "your session is live", which is true and unverifiable.
    get "/account", AccountController, :show
    post "/account/profile", AccountController, :update_profile
    post "/account/emails", AccountController, :add_alias
    post "/account/entities", AccountController, :add_entity
    post "/account/entities/:entity_id/members", AccountController, :add_member
  end

  # The lender's screen. Browser pipeline plus the cookie->session bridge, so
  # the LiveView can see who is connected.
  scope "/", IdDidiShWeb do
    pipe_through [:browser, IdDidiShWeb.Plugs.PutDidiToken]

    live "/keys", KeysLive
  end

  # The headless API — the contract consumers call from their own UIs.
  scope "/api", IdDidiShWeb do
    pipe_through :api

    post "/magic-links", MagicLinkController, :create
    post "/magic-links/redeem", MagicLinkController, :redeem
    post "/session/refresh", SessionController, :refresh
    delete "/session", SessionController, :delete
    get "/me", MeController, :show
  end

  # Server-to-server only. The pipeline REJECTS a user session rather than
  # ignoring it — see Plugs.RequireApp for why.
  pipeline :api_app do
    plug :accepts, ["json"]
    plug IdDidiShWeb.Plugs.RequireApp
  end

  scope "/api/internal", IdDidiShWeb do
    pipe_through :api_app

    post "/resolve", ResolveController, :create
  end

  # Entities — the flat tenancy primitive. Membership is required for reads,
  # admin for writes; both resolved via Entities.effective_role/2.
  scope "/api", IdDidiShWeb do
    pipe_through :api_authed

    get "/entities", EntityController, :index
    post "/entities", EntityController, :create
    get "/entities/:id", EntityController, :show

    get "/entities/:entity_id/members", EntityController, :list_members
    post "/entities/:entity_id/members", EntityController, :add_member
    # Returns also_member_of — the removal disclosure is part of the contract,
    # not a UI nicety. See EntityController's moduledoc.
    delete "/entities/:entity_id/members/:didi_id", EntityController, :delete_member

    # The lender's surface: paste, lend, watch, take back. No action here can
    # emit a credential's value — see CredentialController's moduledoc.
    get "/credentials", CredentialController, :index
    post "/credentials", CredentialController, :create
    delete "/credentials/:id", CredentialController, :delete
    get "/credentials/:credential_id/usage", CredentialController, :usage
    post "/credentials/:credential_id/cascades", CredentialController, :lend
    delete "/cascades/:id", CredentialController, :end_cascade
    delete "/cascades/:id/loans/:entity_id", CredentialController, :end_loan
  end

  scope "/.well-known", IdDidiShWeb do
    pipe_through :api

    get "/jwks.json", JWKSController, :show
  end

  # Enable LiveDashboard and Swoosh mailbox preview in development
  if Application.compile_env(:id_didi_sh, :dev_routes) do
    # If you want to use the LiveDashboard in production, you should put
    # it behind authentication and allow only admins to access it.
    # If your application does not have an admins-only section yet,
    # you can use Plug.BasicAuth to set up some basic authentication
    # as long as you are also using SSL (which you should anyway).
    import Phoenix.LiveDashboard.Router

    scope "/dev" do
      pipe_through :browser

      live_dashboard "/dashboard", metrics: IdDidiShWeb.Telemetry
      forward "/mailbox", Plug.Swoosh.MailboxPreview
    end
  end
end
