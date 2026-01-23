#!/bin/bash
set -e

# ============================================================================
# Codebase State Manager - UV Setup Script
#
# Configuração do ambiente de desenvolvimento usando uv
# https://docs.astral.sh/uv/
#
# Usage:
#   ./scripts/setup.sh           # Instalação padrão com dev dependencies
#   ./scripts/setup.sh --prod    # Apenas dependências de produção
#   ./scripts/setup.sh --help    # Mostrar ajuda
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

# Cores para output
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

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

show_help() {
    cat << EOF
Codebase State Manager - UV Setup Script

Usage: $0 [OPTIONS]

Options:
    --prod      Instalar apenas dependências de produção (sem dev)
    --sync      Forçar resincronização do lockfile
    --help      Mostrar esta mensagem de ajuda

Environment Variables:
    UV_PYTHON       Versão do Python a usar (default: 3.10)
    VIRTUAL_ENV     Caminho para o virtualenv (default: .venv)

Examples:
    $0                      # Instalação completa com dev
    $0 --prod               # Apenas produção
    UV_PYTHON=3.11 $0       # Usar Python 3.11

Para mais informações sobre uv, consulte: https://docs.astral.sh/uv/
EOF
}

check_uv_installed() {
    if ! command -v uv &> /dev/null; then
        log_error "uv não está instalado!"
        log_info "Instale uv com:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
        echo "Ou usando pip:"
        echo "  pip install uv"
        exit 1
    fi

    UV_VERSION=$(uv --version 2>/dev/null | head -n1)
    log_info "uv encontrado: $UV_VERSION"
}

check_uvx_installed() {
    if ! command -v uvx &> /dev/null; then
        log_warn "uvx não está instalado. Algumas funcionalidades podem não estar disponíveis."
        log_info "uvx será instalado automaticamente ao usar ferramentas temporárias."
    else
        UVX_VERSION=$(uvx --version 2>/dev/null | head -n1)
        log_info "uvx encontrado: $UVX_VERSION"
    fi
}

check_python_version() {
    local python_version="${UV_PYTHON:-3.10}"
    log_info "Verificando Python $python_version..."

    if ! uv python list | grep -q "cpython-$python_version"; then
        log_warn "Python $python_version não encontrado via uv"
        log_info "Tentando usar Python disponível no sistema..."

        if command -v python3 &> /dev/null; then
            local sys_py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            log_info "Usando Python do sistema: $sys_py_version"
        fi
    else
        log_info "Python $python_version disponível"
    fi
}

create_venv() {
    local python_version="${UV_PYTHON:-3.10}"

    log_step "Criando virtualenv com Python $python_version..."

    if [ -d "$VENV_DIR" ]; then
        log_info "Virtualenv já existe em $VENV_DIR"
        read -p "Deseja recriar? (s/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Ss]$ ]]; then
            log_info "Removendo virtualenv existente..."
            rm -rf "$VENV_DIR"
        else
            log_info "Usando virtualenv existente"
            return 0
        fi
    fi

    uv venv "$VENV_DIR" --python "$python_version"
    log_info "Virtualenv criado com sucesso"
}

install_dependencies() {
    local install_dev=true
    local force_sync=false

    for arg in "$@"; do
        case $arg in
            --prod)
                install_dev=false
                shift
                ;;
            --sync)
                force_sync=true
                shift
                ;;
        esac
    done

    log_step "Instalando dependências..."

    if [ "$force_sync" = true ]; then
        log_info "Forçando resincronização (--sync)..."
    fi

    if [ "$install_dev" = true ]; then
        log_info "Instalando dependências de produção + desenvolvimento..."
        if [ "$force_sync" = true ]; then
            uv sync --extra dev
        else
            uv pip install --editable .[dev]
        fi
    else
        log_info "Instalando apenas dependências de produção..."
        if [ "$force_sync" = true ]; then
            uv sync
        else
            uv pip install -e .
        fi
    fi

    log_info "Dependências instaladas com sucesso"
}

verify_installation() {
    log_step "Verificando instalação..."

    local errors=0

    uv run python -c "import mcp_server; print('  mcp_server: OK')" || {
        log_error "Falha ao importar mcp_server"
        errors=$((errors + 1))
    }

    uv run python -c "import git; print('  GitPython: OK')" || {
        log_error "Falha ao importar GitPython"
        errors=$((errors + 1))
    }

    uv run python -c "import neo4j; print('  neo4j: OK')" || {
        log_error "Falha ao importar neo4j"
        errors=$((errors + 1))
    }

    if [ $errors -eq 0 ]; then
        log_info "Verificação completa - todas as dependências OK"
        return 0
    else
        log_error "$errors erro(s) encontrado(s) na verificação"
        return 1
    fi
}

show_next_steps() {
    echo ""
    log_info "========================================"
    log_info "Configuração concluída!"
    log_info "========================================"
    echo ""
    log_info "Próximos passos:"
    echo ""
    echo -e "  ${BLUE}1. Ativar o virtualenv:${NC}"
    echo "     source .venv/bin/activate"
    echo ""
    echo -e "  ${BLUE}2. Executar testes:${NC}"
    echo "     uv run pytest tests/"
    echo ""
    echo -e "  ${BLUE}3. Executar com desenvolvimento:${NC}"
    echo "     uv run python -m src.mcp_server"
    echo ""
    echo -e "  ${BLUE}4. Usar uvx para ferramentas temporárias:${NC}"
    echo "     uvx ruff check ."
    echo "     uvx mypy src/"
    echo ""
    echo -e "  ${BLUE}5. Instalar ferramenta globalmente:${NC}"
    echo "     uv tool install ruff"
    echo ""
    log_info "Documentação: https://docs.astral.sh/uv/"
    echo ""
}

main() {
    local show_help_flag=false

    for arg in "$@"; do
        case $arg in
            --help)
                show_help_flag=true
                ;;
        esac
    done

    if [ "$show_help_flag" = true ]; then
        show_help
        exit 0
    fi

    echo ""
    log_info "========================================"
    log_info "Codebase State Manager - UV Setup"
    log_info "========================================"
    echo ""

    check_uv_installed
    check_uvx_installed
    check_python_version
    create_venv
    install_dependencies "$@"
    verify_installation || true
    show_next_steps
}

main "$@"
