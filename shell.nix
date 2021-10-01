{ pkgs ? import <nixos-unstable> {} }:
pkgs.mkShell {
    # nativeBuildInputs is usually what you want -- tools you need to run
    nativeBuildInputs = [ pkgs.python39 pkgs.python39Packages.poetry ];
}
