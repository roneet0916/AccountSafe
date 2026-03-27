@echo off
REM ============================================================================
REM AccountSafe Test Runner
REM ============================================================================
REM Usage:
REM   run_tests.bat             Run all tests
REM   run_tests.bat backend     Run backend tests only
REM   run_tests.bat frontend    Run frontend tests only
REM
REM Exit codes:
REM   0  All tests passed
REM   1  Backend tests failed
REM   2  Frontend tests failed
REM   3  Both failed
REM ============================================================================

setlocal EnableDelayedExpansion

set BACKEND_FAILED=0
set FRONTEND_FAILED=0
set RUN_BACKEND=1
set RUN_FRONTEND=1

if "%1"=="backend"  set RUN_FRONTEND=0
if "%1"=="frontend" set RUN_BACKEND=0

set SCRIPT_DIR=%~dp0

echo.
echo ============================================================================
echo   AccountSafe Test Suite
echo ============================================================================
echo.

REM ============================================================================
REM BACKEND TESTS
REM ============================================================================

if %RUN_BACKEND%==1 (
    echo ----------------------------------------------------------------------------
    echo   BACKEND  ^|  Django + pytest
    echo ----------------------------------------------------------------------------
    echo.

    cd /d "%SCRIPT_DIR%..\backend"

    echo Installing test dependencies...
    pip install pytest pytest-django factory-boy pytest-cov -q 2>nul

    echo Running backend tests...
    echo.

    pytest -v
    if errorlevel 1 (
        echo.
        echo   [FAIL] Backend tests failed.
        set BACKEND_FAILED=1
    ) else (
        echo.
        echo   [PASS] Backend tests passed.
    )

    cd /d "%SCRIPT_DIR%"
    echo.
)

REM ============================================================================
REM FRONTEND TESTS
REM ============================================================================

if %RUN_FRONTEND%==1 (
    echo ----------------------------------------------------------------------------
    echo   FRONTEND  ^|  React + Jest
    echo ----------------------------------------------------------------------------
    echo.

    cd /d "%SCRIPT_DIR%..\frontend"

    if not exist "node_modules" (
        echo Installing frontend dependencies...
        call npm install
    )

    echo Running frontend tests...
    echo.

    set CI=true
    call npm test -- --watchAll=false --passWithNoTests
    if errorlevel 1 (
        echo.
        echo   [FAIL] Frontend tests failed.
        set FRONTEND_FAILED=1
    ) else (
        echo.
        echo   [PASS] Frontend tests passed.
    )

    cd /d "%SCRIPT_DIR%"
    echo.
)

REM ============================================================================
REM SUMMARY
REM ============================================================================

echo ============================================================================
echo   Results
echo ============================================================================
echo.

if %RUN_BACKEND%==1 (
    if %BACKEND_FAILED%==0 (
        echo   Backend  : PASS
    ) else (
        echo   Backend  : FAIL
    )
)

if %RUN_FRONTEND%==1 (
    if %FRONTEND_FAILED%==0 (
        echo   Frontend : PASS
    ) else (
        echo   Frontend : FAIL
    )
)

echo.

set /a EXIT_CODE=0
if %BACKEND_FAILED%==1  set /a EXIT_CODE+=1
if %FRONTEND_FAILED%==1 set /a EXIT_CODE+=2

if %EXIT_CODE%==0 (
    echo   All tests passed.
) else (
    echo   One or more test suites failed. Review the output above before deploying.
)

echo.
echo ============================================================================
echo.

exit /b %EXIT_CODE%
