{ buildPythonPackage, fetchPypi, pygments }:

buildPythonPackage rec {
  pname = "pygments-graphql";
  version = "1.0.0";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-ozB3jVPQ8rl+nEJXOSbabW89bhl0i6sbN01G2xFnuaQ=";
  };

  propagatedBuildInputs = [ pygments ];

  pythonImportsCheck = [ "pygments_graphql" ];
}
