{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-PyYAML";
  version = "6.0.0";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-PTWR3fxIj8ML48UGoMD+VNqWj+mNi3arEuWdRVMw/8o=";
  };

  pythonImportsCheck = [ "yaml-stubs" ];
}
