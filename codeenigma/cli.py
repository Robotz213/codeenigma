"""
CLI interface for CodeEnigma
"""

import shutil
import subprocess
import traceback
from datetime import UTC, datetime
from os import environ
from pathlib import Path
from string import Template

import typer
from rich.console import Console
from rich.panel import Panel

from codeenigma import __version__
from codeenigma.bundler.poetry import PoetryBundler
from codeenigma.constants import EXTENSION_COMPILED_MODULE
from codeenigma.extensions import ExpiryExtension
from codeenigma.orchestrator import Orchestrator
from codeenigma.private import NONCE, SECRET_KEY
from codeenigma.runtime.cython.builder import CythonRuntimeBuilder
from codeenigma.strategies import CodeEnigmaObfuscationStrategy

app = typer.Typer(
    name="codeenigma",
    help="CodeEnigma: Securely obfuscate and distribute your Python code.",
    add_completion=True,
)
console = Console()


def display_banner():
    """Display a nice CLI banner."""
    console.print(
        Panel.fit(
            """
[bold green]A lightweight, open-source tool for Python code obfuscation. CodeEnigma helps protect your logic from reverse engineering and unauthorized access, making it secure to distribute your Python applications.[/bold green]

📝 [bold yellow]License:[/bold yellow] MIT
👤 [bold yellow]Author:[/bold yellow] KrishnanSG
📦 [bold yellow]Repo:[/bold yellow] https://github.com/KrishnanSG/codeenigma
""",
            title=f"🚀 [bold cyan]Welcome to CodeEnigma v{__version__}[/bold cyan]",
            border_style="bright_magenta",
        )
    )


@app.command()
def obfuscate(
    module_path: str = typer.Argument(
        ..., help="Path to the Python module to obfuscate"
    ),
    expiration_date: str = typer.Option(
        None,
        "--expiration",
        "-e",
        help="Expiration date for the obfuscated code (YYYY-MM-DD)",
    ),
    output_dir: str = typer.Option(
        "cedist",
        "--output",
        "-o",
        "--dist",
        help="Output directory for obfuscated files",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Obfuscate a Python module and its dependencies."""
    display_banner()

    module_path = Path(module_path)
    if not module_path.exists():
        console.print(
            f"[bold red]Error: Module path '{module_path}' does not exist[/bold red]"
        )
        raise typer.Exit(1)

    if not module_path.is_dir():
        console.print(
            "[bold red]Error: Module path must be a directory containing Python files[/bold red]"
        )
        raise typer.Exit(1)

    if expiration_date:
        try:
            expiration_date = datetime.fromisoformat(expiration_date)
        except ValueError:
            console.print(
                "[bold red]Error: Invalid expiration date format. Please use YYYY-MM-DD HH:MM:SS+0000[/bold red]"
            )
            raise typer.Exit(1) from None

    if expiration_date and expiration_date < datetime.now(tz=UTC):
        console.print(
            "[bold red]Error: Expiration date must be in the future[/bold red]"
        )
        raise typer.Exit(1)

    strategy = CodeEnigmaObfuscationStrategy(SECRET_KEY, NONCE)
    bundler = PoetryBundler()
    extensions = []

    if expiration_date:
        e = ExpiryExtension(expiration_date)
        extensions.append(e)

    r = CythonRuntimeBuilder(strategy, bundler, extensions)

    o = Orchestrator(Path(module_path), strategy, r, output_dir=Path(output_dir))

    try:
        if verbose:
            console.print("\n[bold]Starting codeenigma...[/bold]")
        o.run()

        if verbose:
            console.print(
                "\n[bold green]Obfuscation completed successfully![/bold green]"
            )
            console.print(f"Output files saved to: {Path(output_dir).resolve()}")

    except Exception as e:
        exc = "\n".join(traceback.format_exception(e))
        console.print(f"\n[bold red]Error during obfuscation:[/bold red] {exc}")
        raise typer.Exit(1) from e


@app.command()
def build(
    module_path: str = typer.Argument(
        ..., help="Path to the Python module to obfuscate"
    ),
    exe_name: str = typer.Option(
        "MyApp",
        "--exe-name",
        "-exe",
        help="Name of the output executable",
    ),
    expiration_date: str = typer.Option(
        None,
        "--expiration",
        "-e",
        help="Expiration date for the obfuscated code (YYYY-MM-DD)",
    ),
    output_dir: str = typer.Option(
        "cedist",
        "--output",
        "-o",
        "--dist",
        help="Output directory for obfuscated files",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
) -> None:
    """Obfuscate a Python module and its dependencies."""

    environ.update({"CODEENIGMA_BUILDING_EXE": "1"})

    obfuscate(
        module_path=module_path,
        expiration_date=expiration_date,
        output_dir=output_dir,
        verbose=verbose,
    )

    try:
        console.print("\n[bold]Starting pyinstaller build...[/bold]")

        module_path: Path = Path(module_path)
        current_dir = Path.cwd()
        module_name = module_path.parent.name
        parent = Path(__file__).parent
        templates_path = parent.joinpath("templates")

        dist_path = current_dir.joinpath(output_dir)
        path_module_obfuscated = dist_path.joinpath(module_name)
        runtime_path = dist_path.joinpath("codeenigma_runtime")
        dest = path_module_obfuscated.joinpath("codeenigma_runtime")

        old_text = "from codeenigma_runtime"
        new_text = f"from {module_name}.codeenigma_runtime"
        for file in path_module_obfuscated.rglob("*.py"):
            file_text = file.read_text()
            text_replaced = file_text.replace(old_text, new_text)
            file.write_text(text_replaced)

        shutil.move(runtime_path, dest)

        path_spec_template = templates_path.joinpath("pyinstaller.spec.template")

        glob_file = dest.glob(f"codeenigma_runtime*.{EXTENSION_COMPILED_MODULE}")
        runtime_compiled = list(glob_file)[-1]
        t = Template(path_spec_template.read_text(encoding="utf-8"))

        module_spec = t.safe_substitute(
            {
                "entry_point": repr(str(Path(module_path).resolve())),
                "compiled_codeenigma": repr(str(runtime_compiled.resolve())),
                "exe_name": exe_name,
            }
        )

        dest_spec_file = dist_path.joinpath(f"{module_name}.spec")
        with dest_spec_file.open("w", encoding="utf-8") as f:
            f.write(module_spec)

        subprocess.run(
            ["pyinstaller", str(dest_spec_file), "--distpath", str(dist_path)],
            check=True,
        )

    except Exception as e:
        exc = "\n".join(traceback.format_exception(e))
        console.print(f"\n[bold red]Error during build:[/bold red] {exc}")
        raise typer.Exit(1) from e

    finally:
        environ.update({"CODEENIGMA_BUILDING_EXE": "0"})


@app.command()
def version() -> None:
    """Show the version of CodeEnigma."""
    console.print(f"CodeEnigma CLI v{__version__}")


if __name__ == "__main__":
    app()
