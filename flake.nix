{
  description = "terminology-forge";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, pyproject-nix, uv2nix, pyproject-build-systems, ... }:
    let
      lib = nixpkgs.lib;
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
      forAll = f: lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});

      # Only include files the build needs, so editing devenv.nix,
      # .devenv/, tests, etc. doesn't trigger a rebuild.
      workspaceRoot = lib.fileset.toSource {
        root = ./.;
        fileset = lib.fileset.unions [
          ./pyproject.toml
          ./uv.lock
          ./myapp
          # ./README.md   # add anything pyproject.toml references (readme, license)
        ];
      };

      workspace = uv2nix.lib.workspace.loadWorkspace { inherit workspaceRoot; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      # Per-package fixes go here (see "When a dependency fails to build")
      overrides = final: prev: { };

      pythonSetFor = pkgs:
        (pkgs.callPackage pyproject-nix.build.packages {
          python = pkgs.python312;
        }).overrideScope (lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
          overrides
        ]);
    in
    {
      packages = forAll (pkgs:
        let
          pythonSet = pythonSetFor pkgs;
          util = pkgs.callPackages pyproject-nix.build.util { };
        in
        {
          default = util.mkApplication {
            venv = pythonSet.mkVirtualEnv "myapp-env" workspace.deps.default;
            package = pythonSet.myapp;
          };
        });

      nixosModules.default = import ./module.nix self;

      nixosConfigurations.server = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";   # change to aarch64-linux if your server is ARM
        modules = [
          self.nixosModules.default
          ./hosts/server/configuration.nix
        ];
      };
    };
}
