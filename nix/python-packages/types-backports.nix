{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-backports";
  version = "0.1.3";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-9LcgbAc9+I1iAIkePSdQYYX9YM2mb7KJc3svqSwAEM8=";
  };

  pythonImportsCheck = [ "backports-stubs" ];
}
