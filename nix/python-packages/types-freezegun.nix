{ buildPythonPackage, fetchPypi }:

buildPythonPackage rec {
  pname = "types-freezegun";
  version = "1.1.3";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-6xLNRgy57ZoGdMbyx5l2P4VlDbWbAPKRj/VbwR4b4q4=";
  };

  pythonImportsCheck = [ "freezegun-stubs" ];
}
