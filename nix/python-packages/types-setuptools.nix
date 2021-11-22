{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-setuptools";
  version = "57.4.2";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-VJmg9CkoHRo6qUlMebZZmrNW3+bTk4JUJrx0nkjqG/g=";
  };

  pythonImportsCheck = [ "setuptools-stubs" ];
}
