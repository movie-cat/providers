{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python310
    pkgs.python310Packages.setuptools
    pkgs.python310Packages.wheel
    pkgs.python310Packages.pip
    pkgs.python310Packages.virtualenv
  ];

  shellHook = ''
    if [ ! -d ".venv" ]; then
      python -m venv .venv
    fi

    source .venv/bin/activate

    pip install --upgrade pip
    pip install -r requirements.txt

    export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc
    ]}
  '';
}
