{ buildPythonPackage
, fetchPypi
, django
, django-stubs-ext
, mypy
, toml
, typing-extensions
, types-pytz
, types-PyYAML
}:

buildPythonPackage rec {
  pname = "django-stubs";
  version = "1.9.0";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-ZkhDCRY2qRf69SVtAoR2VZ3DYP3vkFC234erYbIWB78=";
  };

  propagatedBuildInputs = [
    django django-stubs-ext mypy typing-extensions types-pytz types-PyYAML
  ];

  pythonImportsCheck = [ "django-stubs" ];
}
