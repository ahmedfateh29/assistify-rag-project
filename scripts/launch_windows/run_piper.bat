@echo off
title Assistify Piper
call "%~dp0_env.bat"
cd /d "%REPO_ROOT%"
echo Starting Piper TTS on port 5002...
"C:\Users\a7med\miniconda3\envs\assistify_main\python.exe" -u "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\scripts\run_with_log.py" "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\logs\piper.log" "%PYTHON_EXE%" -u -m uvicorn tts_service.piper_server:app --host 127.0.0.1 --port 5002 --log-level info --timeout-keep-alive 300
pause
