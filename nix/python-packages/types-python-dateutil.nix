{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-python-dateutil";
  version = "2.8.2";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-hKGwn65A1hwB9FDqh81ZQgG76FEaZP7L5DMFG4f7WCw=";
  };

  pythonImportsCheck = [ "dateutil-stubs" ];
}
