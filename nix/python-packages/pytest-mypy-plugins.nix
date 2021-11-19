{ buildPythonPackage
, fetchFromGitHub
, chevron
, decorator
, mypy
, pytest
, pytestCheckHook
, pyyaml
, pystache
}:

buildPythonPackage rec {
  pname = "pytest-mypy-plugins";
  # Using an old version because the current on requires mypy>=0.900.
  version = "1.7.0";

  src = fetchFromGitHub {
    owner = "typeddjango";
    repo = "pytest-mypy-plugins";
    rev = version;
    sha256 = "sha256-C9jIV6NZg5FuFO89VX8tnGWSCHKNBrwSwldy4+su3v4=";
  };

  propagatedBuildInputs = [ decorator mypy pytest pyyaml pystache ];
  checkInputs = [ mypy pytestCheckHook ];
}
