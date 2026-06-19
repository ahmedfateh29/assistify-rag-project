@echo off
title Assistify Ollama
call "%~dp0_env.bat"
cd /d "%REPO_ROOT%"
where "%OLLAMA_EXE%" >nul 2>&1
if not errorlevel 1 goto :run_ollama
if exist "%OLLAMA_EXE%" goto :run_ollama
echo [ERROR] Ollama not found at "%OLLAMA_EXE%"
echo Start the Ollama tray app, install the CLI, or re-run with --no-ollama
pause
exit /b 1
:run_ollama
echo Starting Ollama on port 11434...
"%OLLAMA_EXE%" serve
pause
