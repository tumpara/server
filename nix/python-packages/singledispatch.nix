{ buildPythonPackage, fetchPypi, six }:

buildPythonPackage rec {
  pname = "singledispatch";
  version = "3.7.0";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-waTVwdoxDD/Y/M+41OHLffB2FI/V2FioGeN//+RPMJI=";
  };

  propagatedBuildInputs = [ six ];

  pythonImportsCheck = [ "singledispatch" ];
}
