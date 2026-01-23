#!/bin/bash
set -e

# ============================================================================
# Codebase State Manager - EntryPoint Script
# 
# Este script gerencia o lifecycle do Neo4j e da aplicação Python.
# Funciona em dois modos:
#   1. NEO4J_ENABLED=true  -> Inicia Neo4j internamente, depois a app
#   2. NEO4J_ENABLED=false -> Usa SQLite diretamente, inicia app
# ============================================================================

NEO4J_VERSION="5.24.0"
NEO4J_HOME="/opt/neo4j"
NEO4J_DATA="/data/neo4j"
NEO4J_LOGS="/data/neo4j/logs"
APP_HOME="/app"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

wait_for_neo4j() {
    log_info "Aguardando Neo4j ficar disponível em localhost:7687..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
try:
    s.connect(('localhost', 7687))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
            log_info "Neo4j está disponível!"
            return 0
        fi
        
        log_info "Tentativa $attempt/$max_attempts - Neo4j não pronto ainda..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "Neo4j não ficou disponível após $max_attempts tentativas"
    return 1
}

download_neo4j() {
    if [ -d "$NEO4J_HOME" ]; then
        log_info "Neo4j já instalado em $NEO4J_HOME"
        return 0
    fi
    
    log_info "Baixando Neo4j $NEO4J_VERSION..."
    
    local neo4j_tar="/tmp/neo4j-community-$NEO4J_VERSION.tar.gz"
    
    # Verifica se já foi baixado
    if [ -f "$neo4j_tar" ]; then
        log_info "Arquivo já existe, usando cache..."
    else
        curl -L -o "$neo4j_tar" \
            "https://dist.neo4j.org/neo4j-community-$NEO4J_VERSION-unix.tar.gz" \
            --silent --show-error --fail || {
            log_error "Falha ao baixar Neo4j"
            return 1
        }
    fi
    
    log_info "Extraindo Neo4j..."
    mkdir -p "$NEO4J_HOME"
    tar -xzf "$neo4j_tar" -C /opt && \
        mv /opt/neo4j-community-$NEO4J_VERSION "$NEO4J_HOME" || {
        log_error "Falha ao extrair Neo4j"
        return 1
    }
    
    # Limpa tar
    rm -f "$neo4j_tar"
    
    log_info "Neo4j instalado com sucesso"
}

configure_neo4j() {
    log_info "Configurando Neo4j..."
    
    mkdir -p "$NEO4J_DATA" "$NEO4J_LOGS"
    
    # Configuração minimalista
    cat > "$NEO4J_HOME/conf/neo4j.conf" << EOF
# Neo4j Configuration for Codebase State Manager
dbms.connector.http.listen_address=:7474
dbms.connector.bolt.listen_address=:7687
dbms.memory.heap.initial_size=256m
dbms.memory.heap.max_size=512m
dbms.tx_log.rotation.retention_policy=1 files
dbms.security.auth_enabled=false
EOF
    
    # Configura auth desabilitado para simplificar
    export NEO4J_AUTH="${NEO4J_USER:-neo4j}/${NEO4J_PASSWORD:-password}"
    
    log_info "Neo4j configurado"
}

start_neo4j() {
    log_info "Iniciando Neo4j..."
    
    # Garante que não há processo anterior
    pkill -f "neo4j" 2>/dev/null || true
    sleep 1
    
    # Inicia Neo4j em background
    "$NEO4J_HOME/bin/neo4j" start || {
        log_error "Falha ao iniciar Neo4j"
        return 1
    }
    
    # Espera Neo4j estar pronto
    wait_for_neo4j || {
        log_error "Neo4j não iniciou corretamente"
        return 1
    }
    
    log_info "Neo4j iniciado e disponível"
}

stop_neo4j() {
    log_info "Parando Neo4j..."
    "$NEO4J_HOME/bin/neo4j" stop 2>/dev/null || true
}

cleanup_neo4j() {
    log_info "Limpando processos Neo4j..."
    pkill -f "neo4j" 2>/dev/null || true
}

main() {
    log_info "========================================"
    log_info "Codebase State Manager - Starting..."
    log_info "========================================"
    
    # Trap para cleanup
    trap cleanup_neo4j EXIT INT TERM
    
    # Determina modo de operação
    if [ "${NEO4J_ENABLED:-true}" = "true" ]; then
        log_info "MODO: Neo4j Embedded (primário)"
        
        # Downloads e configura Neo4j
        download_neo4j || {
            log_warn "Falha ao baixar Neo4j, usando SQLite como fallback"
            NEO4J_ENABLED=false
        }
        
        if [ "${NEO4J_ENABLED:-true}" = "true" ]; then
            configure_neo4j
            start_neo4j
        fi
    else
        log_info "MODO: SQLite (fallback)"
    fi
    
    log_info "========================================"
    log_info "Iniciando aplicação Python..."
    log_info "========================================"
    
    # Executa a aplicação
    cd "$APP_HOME"
    exec python3 -m src.mcp_server
}

main "$@"
