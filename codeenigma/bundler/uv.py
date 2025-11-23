import platform
import shutil
import subprocess
from pathlib import Path

import rich

from codeenigma.bundler.base import IBundler

EXTENSION_COMPILED_MODULE = ".so" if platform.system() != "Windows" else ".pyd"


class UVBundler(IBundler):
    @staticmethod
    def remove_readme_before_build(pyproject_path: Path) -> None:
        content = pyproject_path.read_text()
        with open(pyproject_path) as f:
            content = f.read()

        with open(pyproject_path, "w") as f:
            f.write(content.replace('readme = "README.md"', ""))

    def create_wheel(self, module_path: Path, output_dir: Path | None = None, **kwargs):
        pyproject_file = module_path.parent / "pyproject.toml"
        if not pyproject_file.exists():
            raise FileNotFoundError(f"pyproject.toml not found in {module_path.parent}")

        with open(pyproject_file, "rb") as f:
            import tomllib

            content = tomllib.load(f)
            try:
                version = content["project"]["version"]
            except KeyError:
                # fallback for poetry format
                try:
                    version = content["tool"]["poetry"]["version"]
                except KeyError as e:
                    raise Exception(
                        "Invalid pyproject.toml file, missing version"
                    ) from e

        if kwargs.get("remove_readme", True):
            self.remove_readme_before_build(pyproject_file)

        rich.print("[bold blue]Building wheel using uv[/bold blue]")
        subprocess.run(
            ["uv", "pip", "install", "-e", "."],
            cwd=str(module_path.parent),
            check=True,
        )
        subprocess.run(
            ["uv", "run", "python", "-m", "build", "--wheel"],
            cwd=str(module_path.parent),
            check=True,
        )

        dist_path = module_path.parent.joinpath("dist")
        wheel_file = list(dist_path.glob(f"*{version}*.whl"))[-1]
        final_wheel_location = wheel_file

        if output_dir:
            output_dir.mkdir(exist_ok=True)
            final_wheel_location = output_dir.joinpath(wheel_file.name)
            shutil.move(wheel_file, final_wheel_location)

        rich.print(
            f"[green]✓ Wheel built successfully ({final_wheel_location})[/green]"
        )
        return final_wheel_location

    def create_extension(
        self, module_path: Path, output_dir: Path | None = None, **kwargs
    ) -> Path:
        location = (
            module_path
            if module_path.joinpath("setup.py").exists()
            else module_path.parent
        )
        if not location.joinpath("setup.py").exists():
            raise FileNotFoundError(
                f"setup.py not found in {module_path.parent} or {module_path}"
            )

        rich.print("[bold blue]Building extension using uv[/bold blue]")
        try:
            subprocess.run(
                ["uv", "run", "python", "setup.py", "build_ext", "--inplace"],
                cwd=str(location),
                check=True,
            )
        except subprocess.CalledProcessError:
            import sys

            subprocess.run(
                [sys.executable, "setup.py", "build_ext", "--inplace"],
                cwd=str(location),
                check=True,
            )

        module_file = list(location.glob(f"*{EXTENSION_COMPILED_MODULE}"))[-1]
        shutil.rmtree(location / "build")

        final_module_location = module_file
        if output_dir:
            output_dir.mkdir(exist_ok=True)
            shutil.move(module_file, output_dir / module_file.name)
            final_module_location = output_dir / module_file.name

        rich.print(
            f"[green]✓ Extension built successfully ({final_module_location})[/green]"
        )
        return final_module_location
