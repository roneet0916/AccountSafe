#!/bin/bash
# ============================================================================
# AccountSafe Test Runner
# ============================================================================
#
# Usage:
#   ./run_tests.sh              Run all tests
#   ./run_tests.sh backend      Run backend tests only
#   ./run_tests.sh frontend     Run frontend tests only
#   ./run_tests.sh --coverage   Run with coverage reports
#
# Exit codes:
#   0  All tests passed
#   1  Backend tests failed
#   2  Frontend tests failed
#   3  Both failed
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKEND_FAILED=0
FRONTEND_FAILED=0
RUN_BACKEND=1
RUN_FRONTEND=1
COVERAGE_MODE=0

for arg in "$@"; do
    case $arg in
        backend)   RUN_FRONTEND=0 ;;
        frontend)  RUN_BACKEND=0  ;;
        --coverage) COVERAGE_MODE=1 ;;
    esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ============================================================================
# BANNER
# ============================================================================

echo ""
echo "============================================================================"
echo "  AccountSafe Test Suite"
echo "============================================================================"
echo ""

# ============================================================================
# BACKEND TESTS
# ============================================================================

if [ $RUN_BACKEND -eq 1 ]; then
    echo "----------------------------------------------------------------------------"
    echo "  BACKEND  |  Django + pytest"
    echo "----------------------------------------------------------------------------"
    echo ""

    cd "$SCRIPT_DIR/../backend"

    if [ -d "venv" ]; then
        source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true
    fi

    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install pytest pytest-django factory-boy pytest-cov -q 2>/dev/null || true

    echo -e "${YELLOW}Running backend tests...${NC}"
    echo ""

    if [ $COVERAGE_MODE -eq 1 ]; then
        if pytest --cov=api --cov-report=term-missing --cov-report=html -v; then
            echo ""
            echo -e "${GREEN}[PASS] Backend tests passed.${NC}"
        else
            echo ""
            echo -e "${RED}[FAIL] Backend tests failed.${NC}"
            BACKEND_FAILED=1
        fi
    else
        if pytest -v; then
            echo ""
            echo -e "${GREEN}[PASS] Backend tests passed.${NC}"
        else
            echo ""
            echo -e "${RED}[FAIL] Backend tests failed.${NC}"
            BACKEND_FAILED=1
        fi
    fi

    cd "$SCRIPT_DIR"
    echo ""
fi

# ============================================================================
# FRONTEND TESTS
# ============================================================================

if [ $RUN_FRONTEND -eq 1 ]; then
    echo "----------------------------------------------------------------------------"
    echo "  FRONTEND  |  React + Jest"
    echo "----------------------------------------------------------------------------"
    echo ""

    cd "$SCRIPT_DIR/../frontend"

    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        npm install
    fi

    echo -e "${YELLOW}Running frontend tests...${NC}"
    echo ""

    if [ $COVERAGE_MODE -eq 1 ]; then
        if CI=true npm test -- --coverage --watchAll=false --passWithNoTests; then
            echo ""
            echo -e "${GREEN}[PASS] Frontend tests passed.${NC}"
        else
            echo ""
            echo -e "${RED}[FAIL] Frontend tests failed.${NC}"
            FRONTEND_FAILED=1
        fi
    else
        if CI=true npm test -- --watchAll=false --passWithNoTests; then
            echo ""
            echo -e "${GREEN}[PASS] Frontend tests passed.${NC}"
        else
            echo ""
            echo -e "${RED}[FAIL] Frontend tests failed.${NC}"
            FRONTEND_FAILED=1
        fi
    fi

    cd "$SCRIPT_DIR"
    echo ""
fi

# ============================================================================
# SUMMARY
# ============================================================================

echo "============================================================================"
echo "  Results"
echo "============================================================================"
echo ""

if [ $RUN_BACKEND -eq 1 ]; then
    if [ $BACKEND_FAILED -eq 0 ]; then
        echo -e "  Backend  : ${GREEN}PASS${NC}"
    else
        echo -e "  Backend  : ${RED}FAIL${NC}"
    fi
fi

if [ $RUN_FRONTEND -eq 1 ]; then
    if [ $FRONTEND_FAILED -eq 0 ]; then
        echo -e "  Frontend : ${GREEN}PASS${NC}"
    else
        echo -e "  Frontend : ${RED}FAIL${NC}"
    fi
fi

echo ""

EXIT_CODE=0
[ $BACKEND_FAILED -eq 1 ]  && EXIT_CODE=$((EXIT_CODE + 1))
[ $FRONTEND_FAILED -eq 1 ] && EXIT_CODE=$((EXIT_CODE + 2))

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}  All tests passed.${NC}"
else
    echo -e "${RED}  One or more test suites failed. Review the output above before deploying.${NC}"
fi

echo ""
echo "============================================================================"
echo ""

exit $EXIT_CODE
