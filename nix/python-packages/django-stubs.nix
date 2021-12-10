{ buildPythonPackage
, fetchFromGitHub
, django
, mypy
#, pytestCheckHook
#, pytest-mypy-plugins
, toml
, typing-extensions
, types-pytz
, types-PyYAML
}:

let
  version = "1.9.0";

  src = fetchFromGitHub {
    owner = "typeddjango";
    repo = "django-stubs";
    rev = version;
    sha256 = "sha256-8eXdGAHZRGpFTJhx2sU7P0Sa+TqHUKUDwCkQlZnKmkU=";
  };

  django-stubs-ext = buildPythonPackage rec {
    inherit src;

    pname = "django-stubs-ext";
    version = "0.1.0";

    sourceRoot = "source/django_stubs_ext";

    propagatedBuildInputs = [ django toml typing-extensions ];

    # Pytest runs in the main package
    doCheck = false;
  };
in
buildPythonPackage rec {
  inherit version src;

  pname = "django-stubs";

  propagatedBuildInputs = [ django django-stubs-ext mypy typing-extensions types-pytz types-PyYAML ];
#  checkInputs = [ pytestCheckHook pytest-mypy-plugins ];

  # Pytest with Mypy doesn't seem to work yet.
  doCheck = false;
}
