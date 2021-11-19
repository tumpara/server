{ buildPythonPackage
, fetchFromGitHub
, django
, mypy
, pytestCheckHook
, pytest-mypy-plugins
, typing-extensions
, types-pytz
, types-PyYAML
}:

let
  # This is the latest version that doesnt require mypy>=0.900 yet (which isn'T
  # available in nixpkgs).
  version = "1.8.0";

  src = fetchFromGitHub {
    owner = "typeddjango";
    repo = "django-stubs";
    rev = version;
    sha256 = "sha256-eRnD8K3m4uHs35Nv2dwFfUpBT/N+ECG5Bu67yYk7jGE=";
  };

  django-stubs-ext = buildPythonPackage rec {
    inherit src;

    pname = "django-stubs-ext";
    version = "0.1.0";

    sourceRoot = "source/django_stubs_ext";

    propagatedBuildInputs = [ django typing-extensions ];

    # Pytest runs in the main package
    doCheck = false;
  };
in
buildPythonPackage rec {
  inherit version src;

  pname = "django-stubs";

  propagatedBuildInputs = [ django django-stubs-ext mypy typing-extensions types-pytz types-PyYAML ];
  checkInputs = [ pytestCheckHook pytest-mypy-plugins ];
}
