{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-six";
  version = "1.16.2";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-uWvZEfh9FSWMOOEO4/CSHDKIel0i5Bw50VcHtNDk0PE=";
  };

  pythonImportsCheck = [ "six-stubs" ];
}
