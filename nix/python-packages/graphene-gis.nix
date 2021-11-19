{ buildPythonPackage
, fetchFromGitHub
, graphene-django
, graphql-core
, psycopg2
, pytestCheckHook
, pytest-cov
, pytest-django
}:

buildPythonPackage rec {
  pname = "graphene-gis";
  version = "0.0.6";

  src = fetchFromGitHub {
    owner = "EverWinter23";
    repo = "graphene-gis";
    rev = "v${version}";
    sha256 = "sha256-ZyI2yZJ/eenaNqSaQHWVt2WT4+5/0Jsy5yyTwTxnVfo=";
  };

  propagatedBuildInputs = [ graphene-django graphql-core ];
  checkInputs = [ psycopg2 pytestCheckHook pytest-django ];

  disabledTests = [ "test_should_convert_json_to_dict" "test_should_convert_gis_scalar_to_geojson" ];
  pythonImportsCheck = [ "graphene_gis" ];
}
