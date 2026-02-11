# Branch Detection

## Overview

O sistema de detecção de branch garante que o campo `branch_name` na tupla de estado sempre reflita a realidade atual do filesystem, não valores armazenados no banco de dados.

## Problema Resolvido

**Antes (Bug):**
```python
# src/mcp_server/services/state_service.py:173
new_state = State(
    branch_name=current_state.branch_name,  # ← Usava valor do banco (stale)
    ...
)
```

**Depois (Corrigido):**
```python
current_branch_name = branch_detector.get_current_branch_name(project_path)
new_state = State(
    branch_name=current_branch_name,  # ← Usa filesystem reality
    ...
)
```

## Estados Possíveis

| Estado | Descrição | Quando Ocorre |
|--------|-----------|---------------|
| **Branch Normal** | Nome da branch atual (ex: `main`, `feature-x`) | Projeto tem git e branch ativa |
| **not_versioned** | Projeto não possui git | Pasta `.git` não existe |
| **git_error** | Erro ao acessar git | Permissões, lockfile, corrompido |
| **detached_<hash>** | HEAD detached com hash do commit | Checkout de commit específico |
| **detached_head** | HEAD detached sem hash disponível | Erro ao obter hash em detached |

## Arquitetura

```
StateService
    ├── branch_detector: BranchDetectionService
    │       ├── git_manager: GitManager
    │       └── branch_utils: sanitize_branch_name()
    └── _create_state_and_transition_atomic()
            └── branch_detector.get_current_branch_name(project_path)
```

## Fluxo de Detecção

1. **Verificar se é git repo** (`is_git_repo`)
   - Verifica existência de `.git/`
   - Retorna `"not_versioned"` se não for

2. **Obter branch atual** (`get_current_branch`)
   - Executa `git branch --show-current`
   - Se vazio → detached HEAD

3. **Tratar detached HEAD**
   - Tenta obter hash curto: `git rev-parse --short HEAD`
   - Retorna `"detached_<hash>"` ou `"detached_head"`

4. **Sanitizar nome da branch**
   - Remove caracteres especiais
   - Substitui `/` por `_`
   - Trunca se >255 caracteres

5. **Tratar erros**
   - Qualquer exceção → `"git_error"`
   - Log do erro para debugging

## Casos de Uso

### 1. Projeto COM Git (Funcionando Normalmente)

```python
branch_name = "main"  # ou "feature-x", "hotfix/123", etc.
```

**Cenários:**
- Branch normal: `main`, `develop`, `feature/nome`
- Branch com caracteres especiais: `hotfix/ABC-123`, `feature/test_123`
- Branch com nome longo: truncar se necessário (>255 chars)

### 2. Projeto SEM Git (Not Versioned)

```python
branch_name = "not_versioned"
```

**Cenários:**
- Nunca teve git: Projeto novo, sem versionamento
- Git foi removido: Usuário deletou pasta `.git`
- Git corrompido: Pasta `.git` existe mas está corrompida

**Importante:** O sistema continua funcionando normalmente, apenas registrando que não há versionamento.

### 3. Git com ERRO

```python
branch_name = "git_error"
```

**Causas Possíveis:**
- Permissões insuficientes na pasta `.git`
- Git corrompido
- Repository locked
- Outro processo usando git

### 4. Git em DETACHED HEAD

```python
branch_name = "detached_a1b2c3d"  # ou "detached_head"
```

**Detecção:**
```bash
$ git branch --show-current
# (retorna vazio em detached HEAD)
```

### 5. TRANSIÇÕES entre Estados

#### 5A: Com Git → Sem Git
**Sequência:**
1. Estado 5: `branch_name="main"` (com git)
2. Usuário executa: `rm -rf .git`
3. Estado 6: `branch_name="not_versioned"` (sem git)

#### 5B: Sem Git → Com Git
**Sequência:**
1. Estado 3: `branch_name="not_versioned"` (sem git)
2. Usuário executa: `git init && git checkout -b main`
3. Estado 4: `branch_name="main"` (com git)

#### 5C: Mudança de Branch
**Sequência:**
1. Estado 7: `branch_name="main"` (na main)
2. Usuário executa: `git checkout feature-x`
3. Estado 8: `branch_name="feature-x"` (na feature-x)

#### 5D: Mudança para Detached HEAD
**Sequência:**
1. Estado 10: `branch_name="main"` (na main)
2. Usuário executa: `git checkout a1b2c3d` (commit específico)
3. Estado 11: `branch_name="detached_a1b2c3d"` (detached)

## Edge Cases Cobertos

1. **Git worktrees**: `.git` é um arquivo apontando para outro lugar
2. **Git submodules**: `.git` é um arquivo, não pasta
3. **Branch names inválidos**: Emojis, caracteres de controle
4. **Branch names longos**: >255 caracteres
5. **Git bloqueado/lockfile**: `index.lock` presente
6. **Permissões insuficientes**: Sem acesso de leitura a `.git`
7. **Múltiplas versões do git**: Comportamento de `--show-current`

## Validação dos Estados

```python
VALID_BRANCH_PATTERNS = [
    # Com git - branches normais
    r"^[a-zA-Z0-9_-]+$",           # main, develop, feature-x
    r"^[a-zA-Z0-9_/-]+$",          # feature/name, hotfix/123
    
    # Estados especiais
    r"^not_versioned$",            # Sem versionamento git
    r"^git_error$",                # Erro no git
    r"^detached_head$",            # Detached HEAD sem hash
    r"^detached_[a-f0-9]{7,40}$",  # Detached HEAD com hash
]

MAX_BRANCH_NAME_LENGTH = 255
```

## Testes

### Cobertura

- **Unitários:** 16 testes cobrindo todos os cenários
- **Integração:** 2 testes de workflow completo
- **E2E:** 1 teste de múltiplas transições
- **Cobertura de código:** 100% nos módulos novos

### Execução

```bash
# Todos os testes de branch detection
pytest tests/unit/services/test_branch_detection.py -v

# Testes de integração
pytest tests/unit/services/test_state_service_integration.py -v

# Testes end-to-end
pytest tests/integration/test_branch_workflow.py -v

# Todos
pytest tests/unit/services/ tests/integration/test_branch_workflow.py -v
```

## Logging

Mudanças de branch são logadas para debugging:

```python
if current_branch_name != current_state.branch_name:
    logging.info(
        f"Branch changed from '{current_state.branch_name}' to "
        f"'{current_branch_name}' during state transition"
    )
```

Isso permite rastrear quando e como as mudanças de branch ocorrem.

## Compatibilidade

- **Estados antigos:** Mantêm metadados históricos (mesmo que incorretos)
- **Novos estados:** Sempre refletem a realidade do filesystem
- **Projetos sem git:** Funcionam normalmente
- **Erros de git:** Graceful degradation com valores padrão

## Arquivos Modificados/Criados

### Novos
- `src/mcp_server/models/state_model.py` - `BranchState` enum
- `src/mcp_server/utils/branch_utils.py` - `sanitize_branch_name()`
- `src/mcp_server/services/branch_detection_service.py` - `BranchDetectionService`
- `tests/unit/services/test_branch_detection.py` - Testes unitários
- `tests/unit/services/test_state_service_integration.py` - Testes de integração
- `tests/integration/test_branch_workflow.py` - Testes E2E

### Modificados
- `src/mcp_server/services/state_service.py` - Integração com `BranchDetectionService`
- `src/mcp_server/models/__init__.py` - Export `BranchState`
- `src/mcp_server/utils/__init__.py` - Export `sanitize_branch_name`
