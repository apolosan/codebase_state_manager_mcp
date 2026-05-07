import ast
from pathlib import Path


MCP_SERVER_PATH = Path("src/mcp_server/mcp_server.py")


def _load_tree() -> ast.Module:
    return ast.parse(MCP_SERVER_PATH.read_text())


def _tool_registration_count(tree: ast.Module) -> int:
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == "app"
                    and decorator.func.attr == "tool"
                ):
                    count += 1
    return count


def _registered_tool_names(tree: ast.Module) -> list[str]:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "registered_tool_names":
                if not isinstance(node.value, ast.List):
                    raise AssertionError("registered_tool_names must be a list literal")
                return [
                    element.value
                    for element in node.value.elts
                    if isinstance(element, ast.Constant) and isinstance(element.value, str)
                ]
    raise AssertionError("registered_tool_names not found")


class TestMcpServerRegistry:
    def test_registered_tool_names_matches_decorated_tools(self):
        tree = _load_tree()

        decorated_tool_count = _tool_registration_count(tree)
        registered_names = _registered_tool_names(tree)

        assert decorated_tool_count == 25
        assert len(registered_names) == decorated_tool_count

    def test_registered_tool_names_contains_newly_missing_entries(self):
        tree = _load_tree()
        registered_names = set(_registered_tool_names(tree))

        expected_names = {
            "arbitrary_state_transition_tool",
            "get_state_info_tool",
            "get_state_transitions_tool",
            "get_transition_info_tool",
            "track_transitions_tool",
            "get_rewarded_transitions_tool",
            "set_transition_reward_tool",
            "get_current_state_compact_context_tool",
            "get_compact_states_tool",
            "get_current_state_transitions_tool",
        }

        assert expected_names.issubset(registered_names)
