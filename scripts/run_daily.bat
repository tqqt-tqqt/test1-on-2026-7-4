@echo off
REM 券商营业部小红书文案每日生成脚本
REM 由 Windows Task Scheduler 调用，或手动双击运行

cd /d "%~dp0\.."

setlocal
REM 加载 .env 中的环境变量（如果存在）
if exist ".env" (
    for /f "tokens=*" %%a in (.env) do set %%a
)

REM 激活虚拟环境并运行
call .venv\Scripts\activate.bat
python -m xhs_generator.scheduler.task_scheduler --run-once %*
endlocal
