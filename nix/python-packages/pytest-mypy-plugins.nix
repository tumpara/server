{ buildPythonPackage
, fetchFromGitHub
, chevron
, decorator
, mypy
, pytest
, pytestCheckHook
, pyyaml
, regex
}:

buildPythonPackage rec {
  pname = "pytest-mypy-plugins";
  version = "1.9.2";

  src = fetchFromGitHub {
    owner = "typeddjango";
    repo = "pytest-mypy-plugins";
    rev = version;
    sha256 = "sha256-Me5P4Q2M+gGEWlUVgQ0L048rVUOlUzVMgZZcqZPeE4Q=";
  };

  propagatedBuildInputs = [ chevron decorator mypy pytest pyyaml regex ];
  checkInputs = [ mypy pytestCheckHook ];
}
