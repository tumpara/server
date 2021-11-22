{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-pillow";
  version = "8.3.7";

  src = fetchPypi {
    inherit version;
    pname = "types-Pillow";
    sha256 = "sha256-jx1OrtwKqMj+T5Etr/MavXnwSkLZ/aGz8wxEL5Bvz/Q=";
  };

  pythonImportsCheck = [ "PIL-stubs" ];
}
