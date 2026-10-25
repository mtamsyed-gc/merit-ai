@echo off
rem Merit AI self-test: control files, contract pin, a fictitious synthetic pool, gate G1, gate report.
rem Uses synthetic data only. Output: out\selftest_pack and out\selftest_reports next to run.py.
pushd "%~dp0.."
py run.py selftest
echo.
echo Exit code %ERRORLEVEL% (0 = passed). Press any key to close.
pause >nul
popd
