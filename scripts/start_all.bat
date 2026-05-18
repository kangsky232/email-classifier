@echo off
REM 启动所有服务（Windows 版本）
REM 用法: scripts\start_all.bat

echo ========================================
echo   启动邮件分类系统所有服务
echo ========================================

cd /d "%~dp0.."

echo [1/5] 启动 Agent LLM1 (端口 8503)...
start "Agent-LLM1" python scripts\start_agent.py --role llm1 --port 8503 --id acceptor-1
timeout /t 2 >nul

echo [2/5] 启动 Agent LLM2 (端口 8504)...
start "Agent-LLM2" python scripts\start_agent.py --role llm2 --port 8504 --id acceptor-2
timeout /t 2 >nul

echo [3/5] 启动 Agent LLM3 (端口 8505)...
start "Agent-LLM3" python scripts\start_agent.py --role llm3 --port 8505 --id acceptor-3
timeout /t 2 >nul

echo [4/5] 启动 Agent LLM4 (端口 8506)...
start "Agent-LLM4" python scripts\start_agent.py --role llm4 --port 8506 --id acceptor-4
timeout /t 2 >nul

echo [5/5] 启动 API 网关 (端口 5000)...
start "API-Gateway" python scripts\start_gateway.py

echo.
echo ========================================
echo   所有服务已启动！
echo   网关地址: http://localhost:5000
echo   Agent 节点: 8503, 8504, 8505, 8506
echo ========================================
