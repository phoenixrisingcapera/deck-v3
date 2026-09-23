{
  description = "flave — an agent-native document format and desktop publisher";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Tauri v2 on Linux talks to the system WebView (WebKitGTK), so the
        # desktop shell needs GTK's development outputs on PKG_CONFIG_PATH.
        # `nix shell` alone does NOT do this — it puts binaries on PATH and
        # leaves the .pc files behind, which is why pkg-config reports every
        # dependency MISSING outside a devShell. mkShell's buildInputs wire it
        # up correctly, which is the whole reason this flake exists.
        tauriDeps = with pkgs; [
          webkitgtk_4_1
          gtk3
          libsoup_3
          glib-networking   # TLS inside the WebView; without it fetch() fails silently
          openssl
          librsvg           # icon rasterisation at build time
        ];
      in {
        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [ pkg-config rustc cargo nodejs_22 pnpm ];
          buildInputs = tauriDeps;

          shellHook = ''
            echo "flave devshell — $(cargo --version), $(node --version), pnpm $(pnpm --version)"
            for p in webkit2gtk-4.1 gtk+-3.0 libsoup-3.0; do
              printf '  %-18s %s\n' "$p" "$(pkg-config --modversion $p 2>/dev/null || echo MISSING)"
            done
          '';
        };
      });
}
