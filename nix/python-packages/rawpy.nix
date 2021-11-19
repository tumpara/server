{ buildPythonPackage
, fetchFromGitHub
, cython
, libraw
, numpy
, nose
, pkgconf
, opencv4
}:

buildPythonPackage rec {
  pname = "rawpy";
  version = "0.16.0";

  src = fetchFromGitHub {
    owner = "letmaik";
    repo = "rawpy";
    rev = "v${version}";
    sha256 = "sha256-D2SzZsbqKTZ2rfvURF8M6VA3jFSmisA9DEzQtAax4L0=";
  };

  nativeBuildInputs = [ pkgconf ];
  buildInputs = [ cython libraw ];
  propagatedBuildInputs = [ numpy ];
  checkInputs = [ nose opencv4 ];
}
