# Codebase State Manager MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-295%20passed-green.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-85%25-green.svg)]()
[![mypy](https://img.shields.io/badge/mypy-passing-green.svg)]()
[![Bandit](https://img.shields.io/badge/bandit-clean-green.svg)]()

## Status do Desenvolvimento

**Fase 10 (Review & Iteration): CONCLUÍDA** ✓

### Fase 10 - Review & Iteration Completa

**Objetivo:** Revisão final, iteration e refinamento antes de deployment.

**Conquistas da Fase 10:**

1. **Neo4j Integration Tests Habilitados:**
   - 11/11 testes de integração Neo4j agora passam
   - Container Docker Neo4j 5.24 configurado para testes
   - Coverage do neo4j_repository: **31% → 98%** (+67 pontos!)

2. **Edge Cases Testados:**
   - 4 novos testes de edge cases adicionados
   - get_nonexistent_state
   - get_current_with_no_states
   - get_nonexistent_transition
   - create_transition_exception_handling

3. **Coverage Geral:** **90%** (1461 statements, 142 missing)
   - Melhoria de 85% → 90% (+5 pontos)
   - neo4j_repository: 98%
   - sqlite_repository: 94%
   - __main__.py: 98%

4. **Test Suite Completa:** **310 testes passando** (100%)
   - Unit tests: 277
   - Integration tests: 21 (10 SQLite + 11 Neo4j)
   - Security tests: 30+
   - E2E tests: 15
   - Stress tests: 6

### O que foi implementado nas Fases 7-10:

1. **Sistema de Logging Estruturado** (`src/mcp_server/utils/logging.py`):
   - JSONFormatter para saída estruturada em JSON
   - ContextFilter para session_id e state_number
   - Funções: setup_logging, get_logger, set_session_context, set_state_context
   - 12 testes unitários

2. **Módulo de Métricas de Performance** (`src/mcp_server/utils/metrics.py`):
   - Timer para medição precisa de tempo
   - MetricsCollector para contadores e estatísticas de timing
   - PerformanceMonitor para monitoramento de state transitions, DB queries, git operations
   - Decorator @timed_operation para profiling
   - 20 testes unitários

3. **Documentação Completa**:
   - `CHANGELOG.md` - Histórico de versões seguindo Keep a Changelog
   - `API_REFERENCE.md` - Documentação completa da API com exemplos
   - `.git/hooks/pre-commit` - Hook de validação automatizada (black, isort, mypy, bandit, tests)

4. **Melhorias da Fase 8 (Performance & Monitoring)**:
   - **Cobertura de código**: `__main__.py` de 0% para 98% (8 novos testes)
   - **Testes para entry point**: SQLite mode, Neo4j mode, rate limiting, audit logging
   - **Cleanup de recursos**: conftest.py para gerenciamento de conexões SQLite
   - **Resource warnings**: Resolvidos com garbage collection automatizado

### Resumo das Fases Completas:

| Fase | Status | Descrição |
|------|--------|-----------|
| 1 | ✓ Concluída | Docker Integration |
| 2 | ✓ Concluída | Database Schema & Models |
| 3 | ✓ Concluída | Core Tools Implementation |
| 4 | ✓ Concluída | Getters and Queries |
| 5 | ✓ Concluída | Security & Best Practices |
| 6 | ✓ Concluída | Testing Suite |
| 7 | ✓ Concluída | Project Setup & Environment |
| 8 | ✓ Concluída | Performance Optimization & Monitoring |
| 9 | ✓ Concluída | Documentation & Deployment |
| 10 | ✓ Concluída | Review & Iteration |

### Estatísticas do Projeto (Fase 10):

- **Testes**: 310 passando (100%)
  - Unit: 277
  - Integration: 21 (10 SQLite + 11 Neo4j)
  - Security: 30+
  - E2E: 15
  - Stress: 6
- **Coverage**: 90% (1461 statements, 142 missing)
- **neo4j_repository coverage**: 98% (31% → 98%)
- **Build**: ✅ Sucesso (wheel + sdist)
- **Security**: Bandit clean (0 vulnerabilities)
- **Type Safety**: mypy passing (23 source files)
- **Documentação**: API Reference, CHANGELOG, README

### Como Executar:

```bash
# Instalar dependências
./scripts/setup.sh

# Executar todos os testes
./scripts/run_tests.sh

# Executar validação completa (linting + type check + security)
chmod +x .git/hooks/pre-commit
.git/hooks/pre-commit

# Build do pacote
python3 -m build
```

### Arquivos Principais Adicionados:

- `src/mcp_server/utils/logging.py` - Sistema de logging estruturado
- `src/mcp_server/utils/metrics.py` - Métricas de performance
- `tests/unit/test_logging.py` - Testes de logging
- `tests/unit/test_metrics.py` - Testes de métricas
- `CHANGELOG.md` - Histórico de versões
- `API_REFERENCE.md` - Documentação da API
- `.git/hooks/pre-commit` - Hook de validação

---

## uv - Gerenciador de Pacotes Python

Este projeto suporta [uv](https://docs.astral.sh/uv/), um gerenciador de pacotes Python extremamente rápido (escrito em Rust).

### Instalação do uv

```bash
# Usando curl (Linux/macOS)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Ou usando pip
pip install uv
```

### Configuração do Ambiente

```bash
# Instalação completa com dependências de desenvolvimento
./scripts/setup.sh

# Apenas dependências de produção
./scripts/setup.sh --prod

# Forçar resincronização
./scripts/setup.sh --sync
```

### Comandos Úteis

```bash
# Ativar virtualenv
source .venv/bin/activate

# Executar testes
./scripts/run_tests.sh              # Todos os testes
./scripts/run_tests.sh unit         # Apenas unitários
./scripts/run_tests.sh security     # Testes de segurança
./scripts/run_tests.sh --coverage   # Com coverage

# Executar em modo desenvolvimento
./scripts/dev.sh

# Executar comandos diretamente com uv
uv run pytest tests/ -v
uv run python -m src.mcp_server
uv run mypy src/
uv run black --check src/
```

### uvx - Runner de Ferramentas Temporárias

O [uvx](https://docs.astral.sh/uvx/) permite executar ferramentas Python sem instalá-las globalmente:

```bash
# Executar ferramentas temporárias
uvx ruff check src/                 # Linting
uvx mypy src/                       # Type checking
uvx bandit -r src/                  # Security analysis
uvx pre-commit run --all-files      # Pre-commit hooks

# Instalar ferramenta globalmente
uv tool install ruff
uv tool run ruff check src/
```

### Comparação de Performance

| Operação | pip | uv | Speedup |
|----------|-----|-----|---------|
| Install deps | ~30s | ~0.5s | 60x |
| Create venv | ~10s | ~0.1s | 100x |
| Run pytest | - | - | 2-5x faster |

*Valores aproximados, variam conforme ambiente.*

### pyproject.toml

O projeto suporta configuração via `[tool.uv]`:

```toml
[tool.uv]
managed = true
package = "."
```

---

*Desenvolvimento iniciado em 21/01/2026*
*Timeline estimado: 8-12 semanas*
