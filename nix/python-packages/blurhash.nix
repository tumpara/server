{ buildPythonPackage, fetchFromGitHub, cffi, pillow, pytestCheckHook, setuptools-scm }:

buildPythonPackage rec {
  pname = "blurhash";
  version = "1.1.3";

  src = fetchFromGitHub {
    owner = "woltapp";
    repo = "blurhash-python";
    rev = "v${version}";
    sha256 = "sha256-gjw1U69qZ9a8s6so8LG9hq6NU94b/VB0tnFywk7eIwI=";
  };

  SETUPTOOLS_SCM_PRETEND_VERSION = "v${version}";

  nativeBuildInputs = [ setuptools-scm ];
  propagatedBuildInputs = [ cffi pillow ];
  checkInputs = [ pytestCheckHook ];

  pythonImportsCheck = [ "blurhash" ];
}
