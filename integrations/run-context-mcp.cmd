@echo off
rem Lanzador del servidor MCP del Context Manager para Windows.
rem
rem Un IDE (VS Code, Antigravity, Orca...) apunta su configuracion MCP a este
rem archivo. El lanzador situa CONTEXT_MANAGER_HOME en la raiz de la instalacion
rem y usa el Python del entorno virtual (.venv) si existe.
setlocal
set "HERE=%~dp0"
for %%I in ("%HERE%..") do set "CONTEXT_MANAGER_HOME=%%~fI"

set "PY=%CONTEXT_MANAGER_HOME%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%HERE%mcp_server.py" %*
