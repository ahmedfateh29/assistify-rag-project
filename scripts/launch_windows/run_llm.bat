@echo off
title Assistify LLM
call "%~dp0_env.bat"
cd /d "%REPO_ROOT%"
echo Starting LLM on port 8010...
"C:\Users\a7med\miniconda3\envs\assistify_main\python.exe" -u "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\scripts\run_with_log.py" "C:\Users\a7med\Downloads\assistify-rag-project-final-rag-system\assistify-rag-project-final-rag-system\logs\llm.log" "%PYTHON_EXE%" -u -m uvicorn backend.main_llm_server:app --host 0.0.0.0 --port 8010 --log-level info --timeout-keep-alive 300
pause
