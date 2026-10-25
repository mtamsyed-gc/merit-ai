@echo off
rem Merit AI test suite (synthetic data only). All suites must pass before any release.
pushd "%~dp0.."
py tests\run_all.py
echo.
echo Exit code %ERRORLEVEL% (0 = all passed). Press any key to close.
pause >nul
popd
