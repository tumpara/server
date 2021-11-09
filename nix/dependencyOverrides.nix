self: super:

{
  mypy = super.mypy.overridePythonAttrs (old: {
    # https://github.com/NixOS/nixpkgs/blob/e74894146a42ba552ebafa19ab2d1df7ccbc1738/pkgs/development/python-modules/mypy/default.nix#L30-L33
    MYPY_USE_MYPYC = self.stdenv.buildPlatform.is64bit;
  });

  py3exiv2 = super.py3exiv2.overridePythonAttrs (old: {
    buildInputs = let
      boostPython = self.pkgs.boost.override {
        python = self.pkgs.python39;
        enablePython = true;
      };
    in old.buildInputs ++ [
      self.pkgs.exiv2
      boostPython
    ];
  });

  # https://github.com/NixOS/nixpkgs/commit/dfa18fb29d7b167a705b85292f2b7eed033073b1
  sphinx-rtd-theme = super.sphinx-rtd-theme.overridePythonAttrs (old: {
    preBuild = ''
      export CI=1
    '';
  });

  graphene-django = super.graphene-django.overridePythonAttrs (old: {
    postPatch = ''
      substituteInPlace setup.py --replace "singledispatch>=3.4.0.3" "singledispatch"
    '';
  });

  # https://github.com/NixOS/nixpkgs/blob/c21ba4f7bb4a3d621eb1d187e6b5e816bb85380c/pkgs/development/python-modules/django/3.nix
  django = super.django.overridePythonAttrs (old: {
    patches = self.pkgs.substituteAll {
      src = ./django_3_set_geos_gdal_lib.patch;
      geos = self.pkgs.geos;
      gdal = self.pkgs.gdal;
      extension = self.stdenv.hostPlatform.extensions.sharedLibrary;
    };
  });
}
