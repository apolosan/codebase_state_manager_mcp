#!/bin/bash
set -e

# ============================================================================
# Codebase State Manager - Development Runner
#
# Executa a aplicação em modo de desenvolvimento usando uv
# https://docs.astral.sh/uv/
#
# Usage:
#   ./scripts/dev.sh                 # Executar em modo desenvolvimento
#   ./scripts/dev.sh --watch         # Com hot-reload (se disponível)
#   ./scripts/dev.sh --help          # Mostrar ajuda
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

show_help() {
    cat << EOF
Codebase State Manager - Development Runner

Usage: $0 [OPTIONS]

Options:
    --watch     Ativar hot-reload (requer hupper ou similar)
    --help      Mostrar esta mensagem

Environment Variables:
    NEO4J_URI       URI do Neo4j (default: bolt://localhost:7687)
    NEO4J_USER      Usuário do Neo4j (default: neo4j)
    NEO4J_PASSWORD  Senha do Neo4j (default: password)
    DATABASE_URL    URL do SQLite (fallback)

Examples:
    $0                      # Executar normalmente
    NEO4J_URI=bolt://localhost:7687 $0   # Neo4j customizado

Para mais informações sobre uv, consulte: https://docs.astral.sh/uv/
EOF
}

check_uv_installed() {
    if ! command -v uv &> /dev/null; then
        log_error "uv não está instalado!"
        log_info "Execute ./scripts/setup.sh primeiro"
        exit 1
    fi
}

run_dev() {
    local watch=false

    for arg in "$@"; do
        case $arg in
            --watch)
                watch=true
                ;;
            --help)
                show_help
                exit 0
                ;;
        esac
    done

    log_info "========================================"
    log_info "Codebase State Manager - Development"
    log_info "========================================"
    echo ""

    log_info "Ambiente: Desenvolvimento"
    log_info "Python: $(uv run python --version)"
    echo ""

    if [ "$watch" = true ]; then
        log_info "Modo watch ativado..."
        log_warn "Nota: Hot-reload requer dependências adicionais"
        uv run python -m hupper -m src.mcp_server 2>/dev/null || {
            log_warn "hupper não encontrado, executando sem hot-reload..."
            uv run python -m src.mcp_server
        }
    else
        uv run python -m src.mcp_server
    fi
}

main() {
    check_uv_installed
    run_dev "$@"
}

main "$@"
