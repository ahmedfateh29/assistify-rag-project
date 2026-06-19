@echo off
title Assistify Login
call "%~dp0_env.bat"
cd /d "%REPO_ROOT%"
echo Starting Login on port 7001...
"%PYTHON_EXE%" -u -m uvicorn Login_system.login_server:app --host 127.0.0.1 --port 7001 --log-level info --timeout-keep-alive 75
pause
