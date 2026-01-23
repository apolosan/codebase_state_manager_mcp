#!/bin/bash
set -e

# ============================================================================
# Codebase State Manager - Test Runner Script
#
# Executa testes usando uv run para performance máxima
# https://docs.astral.sh/uv/
#
# Usage:
#   ./scripts/run_tests.sh              # Executar todos os testes
#   ./scripts/run_tests.sh unit         # Apenas testes unitários
#   ./scripts/run_tests.sh integration  # Testes de integração
#   ./scripts/run_tests.sh security     # Testes de segurança
#   ./scripts/run_tests.sh performance  # Testes de performance
#   ./scripts/run_tests.sh --coverage   # Com coverage
#   ./scripts/run_tests.sh --verbose    # Output detalhado
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

show_help() {
    cat << EOF
Codebase State Manager - Test Runner Script

Usage: $0 [OPTIONS] [TEST_TYPE]

Options:
    --coverage      Gerar relatório de coverage
    --verbose       Output detalhado (-v)
    --help          Mostrar esta mensagem

Test Types:
    unit            Testes unitários (default)
    integration     Testes de integração
    security        Testes de segurança
    performance     Testes de performance
    e2e             Testes end-to-end
    all             Todos os testes

Examples:
    $0                              # Todos os testes
    $0 unit                         # Apenas unitários
    $0 security --coverage          # Testes de segurança com coverage
    $0 --verbose integration        # Integração com output detalhado

Para mais informações sobre uv, consulte: https://docs.astral.sh/uv/
EOF
}

check_neo4j_available() {
    local neo4j_uri="${NEO4J_URI:-bolt://localhost:7687}"
    local neo4j_user="${NEO4J_USER:-neo4j}"
    local neo4j_password="${NEO4J_PASSWORD:-password}"

    # Try to connect to Neo4j
    if python3 -c "
from src.mcp_server.repositories.neo4j_repository import create_neo4j_repositories
from src.mcp_server.config import Settings

settings = Settings(
    neo4j_enabled=True,
    db_mode='neo4j',
    neo4j_uri='$neo4j_uri',
    neo4j_user='$neo4j_user',
    neo4j_password='$neo4j_password',
    sqlite_path='/tmp/test.db',
)
state_repo, _ = create_neo4j_repositories(
    uri=settings.neo4j_uri,
    user=settings.neo4j_user,
    password=settings.neo4j_password,
    settings=settings,
)
state_repo.driver.close()
" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

start_neo4j_for_tests() {
    log_info "Iniciando Neo4j para testes de integração..."

    local compose_file="${SCRIPT_DIR}/../docker-compose.test.yml"
    if [ -f "$compose_file" ]; then
        cd "$(dirname "$compose_file")"
        docker-compose -f "docker-compose.test.yml" up -d neo4j 2>/dev/null || true

        # Wait for Neo4j to be ready
        log_info "Aguardando Neo4j estar pronto..."
        local max_attempts=30
        local attempt=0
        while [ $attempt -lt $max_attempts ]; do
            if check_neo4j_available; then
                log_info "Neo4j está pronto!"
                export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
                export NEO4J_USER="${NEO4J_USER:-neo4j}"
                export NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
                return 0
            fi
            attempt=$((attempt + 1))
            sleep 2
        done

        log_warn "Neo4j não ficou pronto a tempo, continuando mesmo assim..."
    else
        log_warn "docker-compose.test.yml não encontrado, pulando testes Neo4j..."
    fi
}

stop_neo4j_after_tests() {
    local compose_file="${SCRIPT_DIR}/../docker-compose.test.yml"
    if [ -f "$compose_file" ] && [ "${NEO4J_STARTED:-false}" = "true" ]; then
        log_info "Parando container Neo4j de teste..."
        cd "$(dirname "$compose_file")"
        docker-compose -f "docker-compose.test.yml" down 2>/dev/null || true
    fi
}

run_tests() {
    local test_type="${1:-all}"
    local coverage=false
    local verbose=false
    local extra_args=""

    shift
    while [[ $# -gt 0 ]]; do
        case $1 in
            --coverage)
                coverage=true
                shift
                ;;
            --verbose|-v)
                verbose=true
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    log_info "========================================"
    log_info "Executando testes: $test_type"
    log_info "========================================"

    local test_path=""
    case $test_type in
        unit)
            test_path="tests/unit/"
            ;;
        integration)
            test_path="tests/integration/"
            ;;
        security)
            test_path="tests/security/"
            ;;
        performance)
            test_path="tests/performance/"
            ;;
        e2e)
            test_path="tests/e2e/"
            ;;
        all)
            test_path="tests/"
            ;;
        *)
            log_error "Tipo de teste desconhecido: $test_type"
            show_help
            exit 1
            ;;
    esac

    if [ "$verbose" = true ]; then
        extra_args="-v"
    fi

    if [ "$coverage" = true ]; then
        log_test "Executando com coverage..."
        uv run pytest "$test_path" --cov=src --cov-report=term-missing --cov-report=html $extra_args
    else
        uv run pytest "$test_path" $extra_args
    fi
}

run_quick_tests() {
    log_test "Executando verificação rápida..."

    local result=0

    uv run pytest tests/unit/ -v --tb=short || result=$?

    if [ $result -eq 0 ]; then
        log_info "Testes unitários passaram"
    else
        log_error "Testes unitários falharam"
    fi

    return $result
}

show_test_summary() {
    echo ""
    log_info "========================================"
    log_info "Resumo de testes"
    log_info "========================================"
    echo ""
    echo -e "  ${BLUE}Comandos úteis:${NC}"
    echo ""
    echo "  # Verificar tipos com mypy"
    echo "  uv run mypy src/"
    echo ""
    echo "  # Verificar formatação"
    echo "  uv run black --check src/"
    echo "  uv run isort --check src/"
    echo ""
    echo "  # Verificar segurança"
    echo "  uv run bandit -r src/"
    echo ""
    echo "  # Executar linter"
    echo "  uv run ruff check src/"
    echo ""
}

main() {
    if [[ "$1" == "--help" ]]; then
        show_help
        exit 0
    fi

    local test_type="${1:-all}"
    shift

    check_uv_installed

    # For integration tests, ensure Neo4j is running
    if [[ "$test_type" == "integration" ]] || [[ "$test_type" == "all" ]]; then
        if ! check_neo4j_available; then
            start_neo4j_for_tests
            export NEO4J_STARTED=true
        fi
    fi

    # Ensure Neo4j is stopped on exit
    trap stop_neo4j_after_tests EXIT

    if [[ "$test_type" == "quick" ]]; then
        run_quick_tests
    else
        run_tests "$test_type" "$@"
    fi

    local test_type="${1:-all}"
    shift

    check_uv_installed

    # For integration tests, ensure Neo4j is running
    if [[ "$test_type" == "integration" ]] || [[ "$test_type" == "all" ]]; then
        if ! check_neo4j_available; then
            start_neo4j_for_tests
            export NEO4J_STARTED=true
        fi
    fi

    if [[ "$test_type" == "quick" ]]; then
        run_quick_tests
    else
        run_tests "$test_type" "$@"
    fi

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        show_test_summary
    fi

    exit $exit_code
}

main "$@"
