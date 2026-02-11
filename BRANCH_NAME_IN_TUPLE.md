# Análise do Problema: branch_name na Tupla de Estado

## Resumo Executivo

O MCP Server de codebase-state-manager possui um **bug crítico** onde o campo `branch_name` na tupla de estado não reflete a realidade do versionamento git. O sistema:

1. **Não detecta mudanças de branch** no git (usa valor do banco, não do git atual)
2. **Não suporta projetos sem versionamento git** adequadamente
3. **Não lida com edge cases** como git corrompido, detached HEAD, ou transições entre estados com/sen git

Isso causa inconsistência de metadados e pode levar a comportamentos inesperados.

---

## Problema Identificado

### Comportamento Atual (BUG)

Quando uma nova transição de estado é criada via `new_state_transition()`, o sistema:

1. Recupera o estado atual do repositório (`state_repo.get_current()`)
2. Usa o `branch_name` do estado armazenado no banco de dados
3. Cria o novo estado com essa branch, **ignorando a realidade do filesystem**

### Código Problemático

**Arquivo:** `src/mcp_server/services/state_service.py:173`

```python
new_state = State(
    state_number=0,
    user_prompt=sanitized_prompt,
    branch_name=current_state.branch_name,  # ← PROBLEMA!
    git_diff_info=diff_info,
    hash="",
    file_hashes=file_hashes,
    file_hash_deltas=file_hash_deltas,
)
```

O `current_state.branch_name` vem do estado persistido, não da realidade atual do projeto.

---

## Análise de Todos os Casos de Uso

### Caso 1: Projeto COM Git (Funcionando Normalmente)

**Descrição:** Projeto tem git, está funcionando, branch existe.

**Comportamento Esperado:**
```python
branch_name = "main"  # ou "feature-x", "hotfix/123", etc.
```

**Cenários:**
- **1A - Branch normal:** `main`, `develop`, `feature/nome`
- **1B - Branch com caracteres especiais:** `hotfix/ABC-123`, `feature/test_123`
- **1C - Branch com nome longo:** truncar se necessário (>255 chars)

**Solução:**
```python
def get_branch_name_with_git(self, project_path: Path) -> str:
    if not self.git_manager.is_git_repo(project_path):
        return "not_versioned"
    
    try:
        branch = self.git_manager.get_current_branch(repo_path=project_path)
        # Sanitizar e validar
        if not branch or branch.strip() == "":
            return "detached_head"  # HEAD detached
        return sanitize_branch_name(branch)
    except GitOperationError:
        return "git_error"
```

---

### Caso 2: Projeto SEM Git (Not Versioned)

**Descrição:** Projeto não tem versionamento git (pasta `.git` não existe).

**Comportamento Esperado:**
```python
branch_name = "not_versioned"
```

**Cenários:**
- **2A - Nunca teve git:** Projeto novo, sem versionamento
- **2B - Git foi removido:** Usuário deletou pasta `.git`
- **2C - Git corrompido:** Pasta `.git` existe mas está corrompida

**Solução:**
```python
def get_branch_name_without_git(self) -> str:
    return "not_versioned"
```

**Importante:** O sistema DEVE continuar funcionando normalmente, apenas registrando que não há versionamento.

---

### Caso 3: Git com ERRO

**Descrição:** Git existe mas há erro ao executar comando.

**Causas Possíveis:**
- Permissões insuficientes na pasta `.git`
- Git corrompido
- Repository locked
- Outro processo usando git

**Comportamento Esperado:**
```python
branch_name = "git_error"  # ou último valor conhecido
```

**Solução:**
```python
try:
    branch_name = self.git_manager.get_current_branch(repo_path=project_path)
except GitOperationError as e:
    # Log do erro para debug
    logging.warning(f"Git error getting branch: {e}")
    # Fallback para valor padrão
    branch_name = "git_error"
```

---

### Caso 4: Git em DETACHED HEAD

**Descrição:** HEAD não aponta para nenhuma branch (checkout de commit específico).

**Comportamento Esperado:**
```python
branch_name = "detached_head"  # ou "detached_<hash_curto>"
# Exemplo: "detached_a1b2c3d"
```

**Detecção:**
```bash
$ git branch --show-current
# (retorna vazio em detached HEAD)
```

**Solução:**
```python
def get_branch_name_detached(self, project_path: Path) -> str:
    try:
        branch = self.git_manager.get_current_branch(repo_path=project_path)
        if not branch or branch.strip() == "":
            # Tentar obter hash curto do commit
            try:
                result = self.git_manager._run_git_command(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=project_path
                )
                short_hash = result.stdout.strip()
                return f"detached_{short_hash}"
            except:
                return "detached_head"
        return branch
    except GitOperationError:
        return "git_error"
```

---

### Caso 5: TRANSIÇÕES entre Estados

#### 5A: Com Git → Sem Git (Usuário removeu .git)

**Sequência:**
1. Estado 5: `branch_name="main"` (com git)
2. Usuário executa: `rm -rf .git`
3. Estado 6: `branch_name="not_versioned"` (sem git)

**Impacto:** O sistema deve detectar que `.git` foi removido e atualizar o branch_name.

#### 5B: Sem Git → Com Git (Usuário iniciou git)

**Sequência:**
1. Estado 3: `branch_name="not_versioned"` (sem git)
2. Usuário executa: `git init && git checkout -b main`
3. Estado 4: `branch_name="main"` (com git)

**Impacto:** O sistema deve detectar que git foi inicializado e capturar a branch.

#### 5C: Mudança de Branch (Com Git)

**Sequência:**
1. Estado 7: `branch_name="main"` (na main)
2. Usuário executa: `git checkout feature-x`
3. Estado 8: `branch_name="feature-x"` (na feature-x)

**Impacto:** O sistema deve detectar a mudança de branch e registrar corretamente.

#### 5D: Mudança para Detached HEAD

**Sequência:**
1. Estado 10: `branch_name="main"` (na main)
2. Usuário executa: `git checkout a1b2c3d` (commit específico)
3. Estado 11: `branch_name="detached_a1b2c3d"` (detached)

---

## Solução Completa Proposta

### Arquitetura da Solução

```python
# src/mcp_server/services/state_service.py

from enum import Enum

class BranchState(str, Enum):
    """Estados possíveis para branch_name."""
    NOT_VERSIONED = "not_versioned"
    GIT_ERROR = "git_error"
    DETACHED_HEAD = "detached_head"

class StateService:
    def _get_current_branch_name(
        self, 
        project_path: Path, 
        current_state: Optional[State] = None
    ) -> str:
        """
        Obtém o nome da branch atual do projeto.
        
        Lógica:
        1. Verifica se é git repo
        2. Se for, tenta obter branch atual
        3. Se não for ou der erro, retorna estado apropriado
        4. NUNCA usa valor do estado anterior (evita inconsistência)
        
        Returns:
            - Nome da branch (ex: "main", "feature-x")
            - "not_versioned" se não há git
            - "git_error" se git falhou
            - "detached_<hash>" se em detached HEAD
        """
        # Verificar se é git repo
        if not self.git_manager.is_git_repo(project_path):
            return BranchState.NOT_VERSIONED
        
        try:
            # Tentar obter branch atual
            branch = self.git_manager.get_current_branch(repo_path=project_path)
            
            # Verificar se está em detached HEAD (branch vazio)
            if not branch or branch.strip() == "":
                return self._get_detached_head_name(project_path)
            
            # Sanitizar nome da branch
            return sanitize_branch_name(branch)
            
        except GitOperationError as e:
            logging.warning(f"Git operation error getting branch: {e}")
            return BranchState.GIT_ERROR
        except Exception as e:
            logging.error(f"Unexpected error getting branch: {e}")
            return BranchState.GIT_ERROR
    
    def _get_detached_head_name(self, project_path: Path) -> str:
        """Obtém identificador para detached HEAD."""
        try:
            result = self.git_manager._run_git_command(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=project_path
            )
            short_hash = result.stdout.strip()
            return f"detached_{short_hash}"
        except:
            return BranchState.DETACHED_HEAD
```

### Modificação do _create_state_and_transition_atomic

```python
def _create_state_and_transition_atomic(
    self,
    user_prompt: str,
    diff_info: str,
    current_state: State,
    file_hashes: Optional[dict],
    file_hash_deltas: dict,
    project_path: Path,  # NOVO: Precisamos do path para detectar git
) -> tuple[bool, Optional[State], str]:
    try:
        sanitized_prompt = sanitize_prompt(user_prompt)
    except ValidationError as e:
        return False, None, f"Invalid prompt: {e}"

    # CORREÇÃO: Capturar branch atual do filesystem, não do estado anterior
    current_branch_name = self._get_current_branch_name(project_path, current_state)
    
    # Log para debug de transições
    if current_branch_name != current_state.branch_name:
        logging.info(
            f"Branch changed from '{current_state.branch_name}' to "
            f"'{current_branch_name}' during state transition"
        )

    # Criar novo estado com branch atual (do filesystem, não do banco)
    new_state = State(
        state_number=0,
        user_prompt=sanitized_prompt,
        branch_name=current_branch_name,  # ← CORRIGIDO!
        git_diff_info=diff_info,
        hash="",
        file_hashes=file_hashes,
        file_hash_deltas=file_hash_deltas,
    )
    
    # ... resto do código
```

### Modificação do new_state_transition

```python
def new_state_transition(self, user_prompt: str) -> tuple[bool, Optional[State], str]:
    if not is_initialized(self.settings.docker_volume_name):
        return False, None, "State manager not initialized. Call genesis first."

    current_state = self.state_repo.get_current()
    if not current_state:
        return False, None, "No current state found. Call genesis first."

    volume_codebase = Path(self.settings.docker_volume_name) / "codebase"
    project_path = Path.cwd()

    # CORREÇÃO: Detectar mudança de branch/git antes de criar estado
    current_git_status = self._get_current_branch_name(project_path, current_state)
    
    # Log de transição (útil para debug)
    if current_git_status != current_state.branch_name:
        logging.info(
            f"Environment changed: branch '{current_state.branch_name}' → "
            f"'{current_git_status}'"
        )

    # ... resto do código ...
    
    success, new_state, message = self._create_state_and_transition_atomic(
        user_prompt,
        diff_info,
        current_state,
        None,
        delta_hashes,
        project_path,  # NOVO: Passar project_path
    )
```

---

## Testes Necessários

### Testes Unitários

```python
# tests/unit/test_branch_detection.py

class TestBranchDetection:
    """Testes para detecção de branch em todos os cenários."""
    
    def test_branch_with_git_normal(self, state_service, tmp_path):
        """Caso 1A: Branch normal com git."""
        # Setup: Criar repo git com branch main
        # ...
        branch = state_service._get_current_branch_name(tmp_path)
        assert branch == "main"
    
    def test_branch_with_git_special_chars(self, state_service, tmp_path):
        """Caso 1B: Branch com caracteres especiais."""
        # Setup: Criar branch "feature/ABC-123_test"
        # ...
        branch = state_service._get_current_branch_name(tmp_path)
        assert branch == "feature_ABC-123_test"  # Sanitizado
    
    def test_branch_without_git(self, state_service, tmp_path):
        """Caso 2: Projeto sem git."""
        # Setup: Apenas arquivos, sem .git
        branch = state_service._get_current_branch_name(tmp_path)
        assert branch == "not_versioned"
    
    def test_branch_git_error(self, state_service, tmp_path):
        """Caso 3: Git com erro."""
        # Setup: Criar .git sem permissões
        # ...
        branch = state_service._get_current_branch_name(tmp_path)
        assert branch == "git_error"
    
    def test_branch_detached_head(self, state_service, tmp_path):
        """Caso 4: Detached HEAD."""
        # Setup: Checkout de commit específico
        # ...
        branch = state_service._get_current_branch_name(tmp_path)
        assert branch.startswith("detached_")
    
    def test_transition_git_to_no_git(self, state_service, tmp_path):
        """Caso 5A: Transição com git → sem git."""
        # Estado atual com branch "main"
        current_state = Mock(branch_name="main")
        
        # Remover .git
        shutil.rmtree(tmp_path / ".git")
        
        branch = state_service._get_current_branch_name(tmp_path, current_state)
        assert branch == "not_versioned"
    
    def test_transition_no_git_to_git(self, state_service, tmp_path):
        """Caso 5B: Transição sem git → com git."""
        # Estado atual not_versioned
        current_state = Mock(branch_name="not_versioned")
        
        # Inicializar git
        # ...
        
        branch = state_service._get_current_branch_name(tmp_path, current_state)
        assert branch == "main"
    
    def test_transition_branch_change(self, state_service, tmp_path):
        """Caso 5C: Mudança de branch."""
        # Estado atual na main
        current_state = Mock(branch_name="main")
        
        # Mudar para feature-x
        # ...
        
        branch = state_service._get_current_branch_name(tmp_path, current_state)
        assert branch == "feature-x"
```

### Testes de Integração

```python
# tests/integration/test_branch_transitions.py

def test_full_workflow_with_branch_changes(state_service):
    """Testa workflow completo com mudanças de branch."""
    # 1. Criar estado na main
    # 2. Mudar para feature-x
    # 3. Criar estado (deve ter branch="feature-x")
    # 4. Mudar para develop
    # 5. Criar estado (deve ter branch="develop")
    # 6. Remover .git
    # 7. Criar estado (deve ter branch="not_versioned")
    pass

def test_detached_head_workflow(state_service):
    """Testa workflow em detached HEAD."""
    # 1. Checkout de commit específico
    # 2. Criar estado (deve ter branch="detached_xxxx")
    pass
```

---

## Validação dos Estados Válidos para branch_name

```python
# Valores válidos para branch_name:
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

# Tamanho máximo
MAX_BRANCH_NAME_LENGTH = 255
```

---

## Checklist de Implementação

### Fase 1: Estrutura Base
- [ ] Criar enum `BranchState` com valores especiais
- [ ] Implementar `_get_current_branch_name()` no StateService
- [ ] Implementar `_get_detached_head_name()` auxiliar

### Fase 2: Integração
- [ ] Modificar `_create_state_and_transition_atomic()` para usar nova função
- [ ] Modificar `new_state_transition()` para passar project_path
- [ ] Adicionar logs de mudança de branch

### Fase 3: Testes
- [ ] Criar testes unitários para todos os casos
- [ ] Criar testes de integração para workflows completos
- [ ] Testar edge cases (caracteres especiais, nomes longos)

### Fase 4: Documentação
- [ ] Atualizar docstrings
- [ ] Atualizar documentação técnica
- [ ] Criar exemplos de uso

### Fase 5: Validação
- [ ] Testar em projeto real com git
- [ ] Testar em projeto sem git
- [ ] Testar transições entre branches
- [ ] Testar cenário de erro do git

---

## Conclusão

O problema **ocorre de fato** e afeta múltiplos cenários:

1. **Mudanças de branch não detectadas** → Metadados incorretos
2. **Projetos sem git não suportados** → Sistema pode falhar
3. **Git com erros não tratados** → Exceções não capturadas
4. **Detached HEAD não identificado** → Branch vazia/confusa

A solução proposta cobre **todos os casos identificados** e garante:
- ✓ Branch sempre reflete a realidade do filesystem
- ✓ Projetos sem git funcionam normalmente
- ✓ Erros de git são tratados com graceful degradation
- ✓ Transições entre estados são rastreáveis

**Prioridade**: Alta  
**Complexidade**: Média  
**Risco de Regressão**: Baixo (com testes adequados)

---

## Referências

- `src/mcp_server/services/state_service.py:173` - Código problemático
- `src/mcp_server/services/state_service.py:198-268` - new_state_transition
- `src/mcp_server/services/git_manager.py:435` - `get_current_branch()`
- `src/mcp_server/services/git_manager.py:550` - `is_git_repo()`
- `src/mcp_server/models/state_model.py:24` - Definição do campo `branch_name`
- `src/mcp_server/utils/validation.py:147` - `sanitize_branch_name()`
