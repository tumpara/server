{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-typed-ast";
  version = "1.4.5";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-MQaPlcb6GNW8YLar5WXzzl2Kb28f8Kj6qmG/lwHInls=";
  };

  pythonImportsCheck = [ "typed_ast-stubs" ];
}
