{ buildPythonPackage
, fetchFromGitHub
#, graphene
, mypy
#, pytest
#, pytest-mypy-plugins
}:

buildPythonPackage rec {
  pname = "graphene-types";
  version = "0.15.1";

  src = fetchFromGitHub {
    owner = "whtsky";
    repo = "graphene-types";
    rev = "d33d755dcb399f175c9324de7a04259a7d09dd57";
    sha256 = "sha256-bXfzQwLMbU5YBpkby5LzWHZjwz7Nd+ujWaUxu0lTKWc=";
  };

  propagatedBuildInputs = [ mypy ];
#  checkInputs = [ graphene mypy pytest pytest-mypy-plugins ];

  # Pytest with Mypy doesn't seem to work yet.
  doCheck = false;
}
