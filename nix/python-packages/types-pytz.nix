{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-pytz";
  version = "2021.3.0";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-hqYZZ4NNzuqvmLaQLtg1fv3SYruK/K9LyMzs90hZJ3g=";
  };

  pythonImportsCheck = [ "pytz-stubs" ];
}
