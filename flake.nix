{
  description = "Tumpara server";

  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    let
      dependencyOverrides = import ./nix/dependencyOverrides.nix;
    in
    {
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlay (final: prev: {
          tumparaServer = prev.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            python = prev.python39;
            overrides = prev.poetry2nix.overrides.withDefaults dependencyOverrides;
          };
        })
      ];
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        };
      in
      rec {
        apps = { inherit (pkgs) tumparaServer; };
        defaultApp = apps.tumparaServer;

        packages = {
          inherit (pkgs) tumparaServer;
          tumparaServerEnv = pkgs.poetry2nix.mkPoetryEnv {
            projectDir = ./.;
            python = pkgs.python39;
            overrides = pkgs.poetry2nix.overrides.withDefaults dependencyOverrides;
            editablePackageSources = {
              # Need to use the getEnv hack here because even when using
              # `toString ./.` we get the source folder which was copied into
              # the store.
              tumpara = builtins.getEnv "PWD";
            };
          };
        };

        defaultPackage = packages.tumparaServer;
        devShell = packages.tumparaServerEnv.env.overrideAttrs(old: {
          buildInputs = (old.buildInputs or []) ++ (with pkgs; [
            poetry mypy
          ]);
        });
      }
    ));
}
