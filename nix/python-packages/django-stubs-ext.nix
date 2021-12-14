{ buildPythonPackage
, fetchPypi
, django
, mypy
, toml
, typing-extensions
}:

buildPythonPackage rec {
  pname = "django-stubs-ext";
  version = "0.3.1";

  src = fetchPypi {
    inherit pname version;
    sha256 = "sha256-eDwZjX45pBvguQ/YQ/oncCQ6ZCkir2eb5LGeA7gsjCg=";
  };

  preBuild = ''
    sed -ie 's~license_file = ../LICENSE.txt~~g' setup.cfg
  '';

  propagatedBuildInputs = [ django toml typing-extensions ];

  pythonImportsCheck = [ "django_stubs_ext" ];
}
