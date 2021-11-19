{ buildPythonPackage
, fetchFromGitHub
, django
, pytestCheckHook
, typing-extensions
}:

buildPythonPackage rec {

  src = fetchFromGitHub {
    owner = "typeddjango";
    repo = "django-stubs";
    rev = "372b1340a096ee86e2a3b8148ae591bcc1232dc2";
    sha256 = "sha256-36bcWAN2hzQYajRnayBKi5odmSrYFcnLE8PD7L1Sock=";
  };
  sourceRoot = "source/django_stubs_ext";

  propagatedBuildInputs = [ django typing-extensions ];
  checkInputs = [ pytestCheckHook ];
}
