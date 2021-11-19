{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-toml";
  version = "0.10.1";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-XB+PjVdpI5fI+QK/a02ROglSI1232xfSkIzBEOcGEMs=";
  };

  pythonImportsCheck = [ "toml-stubs" ];
}
