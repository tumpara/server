{ buildPythonPackage
, fetchFromGitHub
, django
, django-filter
, djangorestframework
, graphene
, graphql-core
, mock
, pytest-django
, pytest-runner
, pytestCheckHook
, singledispatch
, text-unidecode
}:

buildPythonPackage rec {
  pname = "graphene-django";
  version = "2.15.0";

  src = fetchFromGitHub {
    owner = "graphql-python";
    repo = "graphene-django";
    rev = "v${version}";
    sha256 = "sha256-ItaLRQfS6m5MahgtxrrmhKuXP6MBdUtZcOUkUouhwlU=";
  };

  postPatch = ''
    substituteInPlace setup.py --replace "singledispatch>=3.4.0.3" "singledispatch"
  '';

  propagatedBuildInputs = [ django graphene graphql-core pytest-runner singledispatch text-unidecode ];
  checkInputs = [ django-filter djangorestframework mock pytestCheckHook pytest-django ];

  disabledTests = [ "test_should_query_postgres_fields" ];
}
