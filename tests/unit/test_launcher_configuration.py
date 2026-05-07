import ast
import json
from pathlib import Path


OPENCODE_PATH = Path("opencode.json")
RUN_LAUNCHER_PATH = Path("run_mcp_server.py")
LEGACY_LAUNCHER_PATH = Path("init_neo4j_and_mcp.py")


def _launcher_import_target(path: Path) -> tuple[str, str]:
    tree = ast.parse(path.read_text())
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                if alias.name == "main":
                    return node.module, alias.name
    raise AssertionError(f"No main import found in {path}")


class TestLauncherConfiguration:
    def test_opencode_uses_canonical_launcher(self):
        payload = json.loads(OPENCODE_PATH.read_text())
        command = payload["mcp"]["codebase-state-manager"]["command"]

        assert command[-1] == "run_mcp_server.py"

    def test_run_launcher_uses_package_main(self):
        module_name, imported_name = _launcher_import_target(RUN_LAUNCHER_PATH)

        assert module_name == "src.mcp_server.__main__"
        assert imported_name == "main"

    def test_legacy_launcher_remains_compatibility_alias(self):
        module_name, imported_name = _launcher_import_target(LEGACY_LAUNCHER_PATH)

        assert module_name == "src.mcp_server.__main__"
        assert imported_name == "main"
