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
            django = super.django_3.override {
              withGdal = true;
            };

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

            blurhash = self.callPackage ./nix/python-packages/blurhash.nix {};
            django-stubs = self.callPackage ./nix/python-packages/django-stubs.nix {};
            django-stubs-ext = self.callPackage ./nix/python-packages/django-stubs-ext.nix {};
            graphene-django = self.callPackage ./nix/python-packages/graphene-django.nix {};
            graphene-gis = self.callPackage ./nix/python-packages/graphene-gis.nix {};
            graphene-types = self.callPackage ./nix/python-packages/graphene-types.nix {};
            inotifyrecursive = self.callPackage ./nix/python-packages/inotifyrecursive.nix {};
            pygments-graphql = self.callPackage ./nix/python-packages/pygments-graphql.nix {};
            pytest-mypy-plugins = self.callPackage ./nix/python-packages/pytest-mypy-plugins.nix {};
            rawpy = self.callPackage ./nix/python-packages/rawpy.nix {};
            singledispatch = self.callPackage ./nix/python-packages/singledispatch.nix {};
            types-backports = self.callPackage ./nix/python-packages/types-backports.nix {};
            types-freezegun = self.callPackage ./nix/python-packages/types-freezegun.nix {};
            types-pillow = self.callPackage ./nix/python-packages/types-pillow.nix {};
            types-python-dateutil = self.callPackage ./nix/python-packages/types-python-dateutil.nix {};
            types-PyYAML = self.callPackage ./nix/python-packages/types-PyYAML.nix {};
            types-six = self.callPackage ./nix/python-packages/types-six.nix {};
          };
        };

        runtimeDependencies = pythonPackages: with pythonPackages; let
          singledispatch = callPackage ./nix/python-packages/singledispatch.nix {};
          graphene-django = callPackage ./nix/python-packages/graphene-django.nix {
            inherit singledispatch;
          };
        in [
          blurhash
          dateutil
          django
          django-cors-headers
          graphene
          graphene-django
          graphene-gis
          inotifyrecursive
          pillow
          psycopg2
          py3exiv2
          rawpy
        ];

        testDependencies = pythonPackages: with pythonPackages; [
          django-stubs
          freezegun
           graphene-types
          hypothesis
          mypy
          pytest
          pytest-cov
          pytest-django
          pytest-mypy-plugins
          pyyaml
          selenium
          types-backports
          types-freezegun
          types-pillow
          types-python-dateutil
          types-setuptools
          types-six
          types-toml
          types-typed-ast
        ];

        developmentDependencies = pythonPackages: with pythonPackages; [
          black
          isort
        ];

        documentationDependencies = pythonPackages: with pythonPackages; [
           pygments-graphql
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

          devEnv = python.withPackages (pythonPackages:
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

        devShell = packages.devEnv.env;
      }
    ));
}
