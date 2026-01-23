# 🚀 Codebase State Manager MCP - Quick Start

## ⚡ Setup Rápido (2 minutos)

### 1. Pré-requisitos
- Docker instalado e rodando
- Opencode configurado

### 2. Configuração Automática
O `opencode.json` já está configurado para:
- ✅ Gerenciar container Neo4j automaticamente
- ✅ Iniciar servidor MCP automaticamente
- ✅ Reutilizar containers existentes

### 3. Como Usar
1. **Reinicie o Opencode**
2. **Aguarde 30-60 segundos** (Neo4j inicializando)
3. **Ferramentas estarão disponíveis automaticamente**

## 🛠️ Ferramentas Disponíveis

| Ferramenta | Descrição |
|------------|-----------|
| `genesis_tool` | Inicializar máquina de estados |
| `get_current_state_number_tool` | Obter estado atual |
| `total_states_tool` | Contar estados totais |
| `new_state_transition_tool` | Criar nova transição |
| `get_current_state_info_tool` | Info completa do estado atual |
| `search_states_tool` | Buscar estados por texto |

## 🔧 Configuração Completa no opencode.json

O arquivo `opencode.json` já está configurado automaticamente:

```json
{
  "mcp": {
    "codebase-state-manager": {
      "type": "local",
      "command": [
        "/root/.local/bin/uv",
        "run",
        "--project",
        "/user/path/codebase_state_manager_mcp",
        "python",
        "init_neo4j_and_mcp.py"
      ],
      "env": {
        "DB_MODE": "neo4j",
        "NEO4J_ENABLED": "true",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
        "LOG_LEVEL": "INFO",
        "RATE_LIMIT_ENABLED": "true",
        "AUDIT_ENABLED": "true"
      },
      "enabled": true
    }
  }
}
```

### Configurações Avançadas (Opcional)

#### Alterar Credenciais Neo4j
```json
"env": {
  "NEO4J_PASSWORD": "sua_senha",
  "NEO4J_USER": "seu_usuario"
}
```

#### Usar SQLite (Sem Docker)
```json
"env": {
  "DB_MODE": "sqlite",
  "NEO4J_ENABLED": "false"
}
```

## 📊 Verificação

```bash
# Container Neo4j
docker ps | grep mcp-neo4j-server

# Volumes persistentes
docker volume ls | grep mcp_neo4j

# Logs
docker logs mcp-neo4j-server
```

## 🎯 Pronto!
**Reinicie o Opencode e use as ferramentas MCP automaticamente!** 🎉</content>
<parameter name="filePath">QUICKSTART.md