#!/usr/bin/env python3
"""Install every catalog package into the backend's virtualenv.

Catalog agents that ship as installable packages resolve their
`output_model` / `tools` by dotted path at run time (e.g.
`my_tagger.models.Tag`). The backend's own venv does not have
them, so `POST /api/run/<agent>` fails with `ModuleNotFoundError`
unless they are installed alongside it.

This is for the "Run locally (no Docker)" workflow. Configs that only
use the framework's own models and tools (such as the framework's
`samples/`) need nothing installed.

The catalog is read from `CATALOG_PATH`, the same variable the backend
uses, and defaults to the repository's `catalog/` folder.

Each package is installed **editable** and with `--no-deps` — its
`agents7` dependency is a local path override that is not on PyPI, so
resolving it here would fail. The remaining third-party dependencies
are installed in a second pass.

Usage (from the repo root or anywhere)::

    CATALOG_PATH=/path/to/your/catalog \\
        uv run python scripts/install_catalog.py
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(os.getenv("CATALOG_PATH", str(ROOT / "catalog")))
BACKEND_VENV = ROOT / "backend" / ".venv"


def backend_python() -> Path:
    """Return the backend venv's interpreter.

    :return: Path to the interpreter inside the backend virtualenv.
    :raises SystemExit: If the virtualenv does not exist yet.
    """
    for rel in ("bin/python", "Scripts/python.exe"):
        candidate = BACKEND_VENV / rel
        if candidate.exists():
            return candidate
    sys.exit(
        f"No virtualenv at {BACKEND_VENV}. Create it first with:\n"
        f"    uv sync --project backend"
    )


def third_party_deps(pyproject: Path) -> list[str]:
    """Return a package's dependencies minus any local-path ones.

    Dependencies overridden by a `[tool.uv.sources]` entry that points
    at a local path (`agents7`) are not on PyPI and are already
    installed in the backend venv, so they are skipped.

    :param pyproject: Path to the package's `pyproject.toml`.
    :return: Requirement strings installable from an index.
    """
    with pyproject.open("rb") as fh:
        config = tomllib.load(fh)

    sources = config.get("tool", {}).get("uv", {}).get("sources", {})
    local = {
        name
        for name, spec in sources.items()
        if isinstance(spec, dict) and "path" in spec
    }
    deps = config.get("project", {}).get("dependencies", [])
    return [dep for dep in deps if _requirement_name(dep) not in local]


def _requirement_name(requirement: str) -> str:
    """Extract the distribution name from a requirement string.

    :param requirement: A PEP 508 requirement, e.g. `agents7>=3.5.0`.
    :return: The normalized distribution name.
    """
    name = requirement
    for sep in ("[", "=", ">", "<", "!", "~", ";", " "):
        name = name.split(sep)[0]
    return name.strip().replace("_", "-").lower()


def run(command: list[str]) -> None:
    """Run a command, echoing it first.

    :param command: The argv list to execute.
    :raises SystemExit: If the command exits non-zero.
    """
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main() -> None:
    """Install every catalog package into the backend venv."""
    python = backend_python()
    packages = sorted(
        d for d in CATALOG.iterdir() if (d / "pyproject.toml").is_file()
    )
    if not packages:
        print(f"No installable packages under {CATALOG}.")
        return

    for package in packages:
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                "-e",
                str(package),
            ]
        )
        deps = third_party_deps(package / "pyproject.toml")
        if deps:
            run(["uv", "pip", "install", "--python", str(python), *deps])

    names = ", ".join(p.name for p in packages)
    print(f"\nInstalled into {BACKEND_VENV}: {names}")


if __name__ == "__main__":
    main()
