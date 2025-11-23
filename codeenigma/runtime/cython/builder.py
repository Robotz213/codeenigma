import platform
import shutil
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from string import Template

import rich

from codeenigma import __version__
from codeenigma.bundler import IBundler
from codeenigma.extensions.base import IExtension
from codeenigma.runtime.base import IRuntimeBuilder
from codeenigma.strategies import BaseObfuscationStrategy


class CythonRuntimeBuilder(IRuntimeBuilder):
    def __init__(
        self,
        strategy: BaseObfuscationStrategy,
        bundler: IBundler,
        extensions: Sequence[IExtension] | None = None,
    ) -> None:
        super().__init__(strategy, bundler, extensions=extensions)

    @staticmethod
    def create_cython_setup(output_path: Path) -> None:
        """Generates a setup.py file for compiling the codeenigma.pyx file"""
        rich.print(
            "[bold blue]Creating setup.py file for compiling the codeenigma.pyx file [/bold blue]"
        )

        path_setup_template = Path(__file__).parent.joinpath("setup.py.template")
        with path_setup_template.open(encoding="utf-8") as f:
            template = Template(f.read())

        setup_code = template.safe_substitute({"version": repr(__version__)})
        output_setup_file = output_path.joinpath("setup.py")
        with output_setup_file.open("w", encoding="utf-8") as f:
            f.write(setup_code)

    @staticmethod
    def create_init_file(output_path: Path) -> None:
        """Creates the __init__.py file"""
        rich.print(
            "[bold blue]Creating codeenigma_runtime/__init__.py file[/bold blue]"
        )

        init_template_path = Path(__file__).parent.joinpath("init.py.template")
        with init_template_path.open(encoding="utf-8") as f:
            template = Template(f.read())

        init_code = template.safe_substitute({"platform": repr(platform.system())})
        output_init_file = output_path.joinpath("__init__.py")
        with output_init_file.open("w", encoding="utf-8") as f:
            f.write(init_code)

        stub_template_path = Path(__file__).parent.joinpath("runtime.pyi.template")
        shutil.copyfile(
            stub_template_path, output_path.joinpath("codeenigma_runtime.pyi")
        )

    @staticmethod
    def create_pyproject_toml(module_file_path: str, output_path: Path) -> None:
        """Creates the pyproject.toml file"""
        rich.print(
            "[bold blue]Creating pyproject.toml file for codeenigma_runtime pkg[/bold blue]"
        )

        template_path = Path(__file__).parent.joinpath("pyproject.toml.template")
        with template_path.open(encoding="utf-8") as f:
            template = Template(f.read())

        pyproject_content = template.safe_substitute(
            {"version": repr(__version__), "module_file_path": str(module_file_path)}
        )

        output_project_file = output_path.joinpath("pyproject.toml")
        with output_project_file.open("w", encoding="utf-8") as f:
            f.write(pyproject_content)

    def prepare_runtime_code(self, runtime_pyx_path: Path) -> None:
        with runtime_pyx_path.open("w", encoding="utf-8") as f:
            code = self.strategy.get_runtime_code()

            for extension in self.extensions:
                code += extension.get_code()

            f.write(code)

    def build(self, output_dir: Path) -> None:
        """Builds the runtime package"""

        rich.print("[bold blue]Building the runtime package[/bold blue]")

        # Building the .so extension
        # Step 1: Creates the codeenigma.pyx and setup files
        output_dir.mkdir(exist_ok=True)
        codeenigma_runtime_pyx = output_dir.joinpath("codeenigma_runtime.pyx")
        self.prepare_runtime_code(codeenigma_runtime_pyx)
        self.create_cython_setup(output_dir)

        # Step 2: Compiles the codeenigma.pyx file using the bundler to .so
        module_file = self.bundler.create_extension(output_dir)

        # Clean up intermediate files
        for temp_file in [
            "setup.py",
            "codeenigma_runtime.pyx",
            "codeenigma_runtime.c",
        ]:
            output_dir.joinpath(temp_file).unlink(missing_ok=True)

        with suppress(Exception):
            output_dir.joinpath("build").rmdir()

        # Packing into codeenigma_runtime wheel

        rich.print("[bold blue]\nPacking the runtime package[/bold blue]")
        # Step 3: Creates the __init__.py file

        codeenigma_runtime_dir = output_dir.joinpath("codeenigma_runtime")
        codeenigma_runtime_dir.mkdir(exist_ok=True)
        path_module = codeenigma_runtime_dir.joinpath(module_file.name)
        shutil.move(module_file, path_module)

        init_path = output_dir.joinpath("codeenigma_runtime")
        self.create_init_file(init_path)

        # Step 4: Creates a pyproject.toml file
        self.create_pyproject_toml(f"codeenigma_runtime/{module_file.name}", output_dir)

        # Step 5. Generates wheel using the bundler
        self.bundler.create_wheel(codeenigma_runtime_dir, output_dir)

        rich.print("[green]✓ Runtime package built successfully[/green]")
