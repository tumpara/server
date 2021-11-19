{
  description = "Tumpara server";

  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        python = pkgs.python39.override {
          packageOverrides = self: super: {
            django = super.django.override {
              withGdal = true;
            };

            # Nixpkgs currently ships an older version of mypy, this is from
            # the upstream for that currently works:
            # https://github.com/python/mypy/pull/11143
            # See also here:
            # https://github.com/NixOS/nixpkgs/pull/140627
#            mypy = super.mypy.overridePythonAttrs (oldAttrs: rec {
#              version = "0.910";
#
#              src = pkgs.fetchFromGitHub {
#                owner = "AWhetter";
#                repo = "mypy";
#                rev = "fix_5701";
#                sha256 = "sha256-kfL9fDhkODqBCYeahF69Ol6L7wkhity3xb46qh91W7c=";
#              };
#
#              # This patch deals with a typing problem with the new versions
#              # of tomli, where mypy hasn't been updated yet:
#              # https://github.com/NixOS/nixpkgs/pull/140627#issuecomment-958286941
#              patches = [ ./nix/mypy_tomli_types.patch ];
#
#              nativeBuildInputs = [ self.types-typed-ast self.types-toml ];
#              propagatedBuildInputs = oldAttrs.propagatedBuildInputs ++ [
#                self.tomli
#              ];
#            });

            # The following overrides are version downgrades that we need to do
            # because we are still following the 2.x version of the GraphQL
            # stack. As soon as we upgrade to 3.x they should no longer be
            # required.

            rx = super.rx.overridePythonAttrs (oldAttrs: rec {
              version = "1.6.1";

              src = pkgs.fetchFromGitHub {
                owner = "ReactiveX";
                repo = "rxpy";
                rev = "${version}";
                sha256 = "sha256-xeq7HAVXG5NuM0NQoaVz3dH00PLiLyUc+5QZoY5RbJE=";
              };
            });

            graphql-core = super.graphql-core.overridePythonAttrs (oldAttrs: rec {
              version = "2.3.2";

              src = pkgs.fetchFromGitHub {
                owner = "graphql-python";
                repo = "graphql-core-legacy";
                rev = "v${version}";
                sha256 = "sha256-I4O+/xNgQARB2hH6OQretgy1DjKyuZP0Ou8ERnuPx0M=";
              };

              propagatedBuildInputs = [ self.promise self.rx ];
              checkInputs = oldAttrs.checkInputs ++ [
                self.pytest-mock
              ];
            });

            graphql-relay = super.graphql-relay.overridePythonAttrs (oldAttrs: rec {
              version = "2.0.1";

              src = self.fetchPypi {
                inherit version;
                pname = "graphql-relay";
                sha256 = "sha256-hwtrUwQSOjigshWnnqzgIazOWkZr9AzTn6GMuFKK+rs=";
              };
            });

            aniso8601 = super.aniso8601.overridePythonAttrs (oldAttrs: rec {
              version = "7.0.0";

              src = self.fetchPypi {
                inherit version;
                pname = "aniso8601";
                sha256 = "sha256-UT0rZje3hTgGrnn/rKbz6HVL3VRwSPXMwUIK7EtxTx4=";
              };
            });

            graphene = super.graphene.overridePythonAttrs (oldAttrs: rec {
              version = "2.1.9";

              src = pkgs.fetchFromGitHub {
                owner = "graphql-python";
                repo = "graphene";
                rev = "v${version}";
                sha256 = "sha256-3/YybycpvbsmAF86YipKjmlhTPDNTusw6y/19IU2TsA=";
              };
            });

            # All the remaining packages in the overlay are ones that are not
            # yet ported in the official nixpkgs repo:

            singledispatch = self.callPackage ./nix/python-packages/singledispatch.nix {};
            inotifyrecursive = self.callPackage ./nix/python-packages/inotifyrecursive.nix {};
            graphene-django = self.callPackage ./nix/python-packages/graphene-django.nix {};
            blurhash = self.callPackage ./nix/python-packages/blurhash.nix {};
            graphene-gis = self.callPackage ./nix/python-packages/graphene-gis.nix {};
            rawpy = self.callPackage ./nix/python-packages/rawpy.nix {};
            django-stubs = self.callPackage ./nix/python-packages/django-stubs.nix {};
            types-pytz = self.callPackage ./nix/python-packages/types-pytz.nix {};
            types-PyYAML = self.callPackage ./nix/python-packages/types-PyYAML.nix {};
            types-toml = self.callPackage ./nix/python-packages/types-toml.nix {};
            types-typed-ast = self.callPackage ./nix/python-packages/types-typed-ast.nix {};
            pytest-mypy-plugins = self.callPackage ./nix/python-packages/pytest-mypy-plugins.nix {};
          };
        };

        runtimeDependencies = pythonPackages: with pythonPackages; let
          singledispatch = callPackage ./nix/python-packages/singledispatch.nix {};
          graphene-django = callPackage ./nix/python-packages/graphene-django.nix {
            inherit singledispatch;
          };
        in [
          blurhash
          django
          django-cors-headers
          graphene
          graphql-core
          graphene-django
          graphene-gis
          inotifyrecursive
          pillow
          psycopg2
          py3exiv2
          dateutil
          rawpy
        ];

        testDependencies = pythonPackages: with pythonPackages; [
          django-stubs
          freezegun
          # graphene-types
          hypothesis
          mypy
          pytest
          pytest-cov
          pytest-django
          pyyaml
          selenium
        ];

        developmentDependencies = pythonPackages: with pythonPackages; [
          black
          isort
        ];

        documentationDependencies = pythonPackages: with pythonPackages; [
          # pygments-graphql
          sphinx
          sphinx_rtd_theme
        ];
      in rec {
        packages = {
#          tumpara = pkgs.python39Packages.buildPythonApplication rec {
#            pname = "tumpara";
#            version = "0.1.0";
#            src = ./.;
#            propagatedBuildInputs = runtimeDependencies pkgs.python39.pkgs;
#            pythonImportsCheck = [ "tumpara" ];
#          };
          tumpara = python.withPackages runtimeDependencies;

          tumparaDevelopmentEnvironment = python.withPackages (pythonPackages:
            (runtimeDependencies pythonPackages)
            ++ (testDependencies pythonPackages)
            ++ (developmentDependencies pythonPackages)
            ++ (documentationDependencies pythonPackages)
          );
        };
        defaultPackage = packages.tumpara;

        apps = {
          tumpara = packages.tumpara;
        };
        defaultApp = apps.tumpara;

        devShell = packages.tumparaDevelopmentEnvironment.env;
      }
    ));
}
