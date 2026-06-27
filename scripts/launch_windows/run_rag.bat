@echo off
title Assistify RAG
call "%~dp0_env.bat"
cd /d "%REPO_ROOT%"
echo Starting RAG on port 7000...
"C:\Users\a7med\miniconda3\envs\assistify_main\python.exe" -u "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\scripts\run_with_log.py" "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\logs\rag.log" "%PYTHON_EXE%" -u -m uvicorn backend.assistify_rag_server:app --host 127.0.0.1 --port 7000 --log-level info --timeout-keep-alive 120
pause
