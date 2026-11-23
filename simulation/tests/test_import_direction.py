"""Enforce inward production imports, including direct package and relative forms."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "koios_sim"
FORBIDDEN = {
    "domain": {"services", "interfaces", "composition"},
    "services": {"interfaces", "composition"},
    "interfaces": {"composition"},
    "composition": set(),
}


def _imported_modules(node: ast.Import | ast.ImportFrom, package: tuple[str, ...]) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level > len(package):
        return []
    prefix = package[:len(package) - node.level + 1] if node.level else ()
    parent = ".".join((*prefix, node.module or "")).rstrip(".")
    return [parent, *(f"{parent}.{alias.name}" for alias in node.names)]


def violations(source: str, package: tuple[str, ...]) -> list[tuple[int, str]]:
    layer = package[1] if len(package) >= 2 else ""
    forbidden = FORBIDDEN.get(layer, set())
    result = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import | ast.ImportFrom):
            for name in _imported_modules(node, package):
                root, _, rest = name.partition(".")
                if root == "koios_sim" and rest.split(".")[0] in forbidden:
                    result.add((node.lineno, name))
    return sorted(result)


@pytest.mark.parametrize(("package", "source"), [
    (("koios_sim", "domain", "traversal"), "import koios_sim.services"),
    (("koios_sim", "domain", "traversal"), "from koios_sim import interfaces as wire"),
    (("koios_sim", "domain", "traversal"), "from ... import composition"),
    (("koios_sim", "domain"), "from ..services.traversal import commands"),
    (("koios_sim", "services"), "from .. import interfaces"),
    (("koios_sim", "interfaces"), "from koios_sim.composition import fixture"),
])
def test_checker_detects_both_import_forms(package: tuple[str, ...], source: str) -> None:
    assert violations(source, package)


@pytest.mark.parametrize(("package", "source"), [
    (("koios_sim", "domain", "traversal"), "from . import world"),
    (("koios_sim", "services", "traversal"), "from ...domain import traversal"),
    (("koios_sim", "interfaces"), "from ..services.traversal import session"),
    (("koios_sim", "composition"), "import koios_sim.interfaces.bridge"),
])
def test_checker_accepts_inward_and_peer_imports(package: tuple[str, ...], source: str) -> None:
    assert not violations(source, package)


def test_production_dependencies_only_point_inward() -> None:
    files = sorted(PACKAGE.rglob("*.py"))
    assert files
    problems = []
    for file in files:
        package = ("koios_sim", *file.parent.relative_to(PACKAGE).parts)
        problems.extend(
            f"{file.relative_to(PACKAGE)}:{line}: {name}"
            for line, name in violations(file.read_text(encoding="utf-8"), package)
        )
    assert not problems, "\n".join(problems)
