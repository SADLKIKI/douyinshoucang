@echo off
chcp 65001 >nul
echo ========================================
echo   DOUYlike - 抖音收藏夹自动更新系统
echo ========================================
echo.

cd /d "%~dp0"

echo [1] 执行完整流水线
echo [2] 仅采集收藏夹
echo [3] 仅转写逐字稿
echo [4] 仅 AI 分析
echo [5] 仅同步飞书
echo [6] 查看统计信息
echo [7] 启动定时任务
echo [8] 设置飞书多维表格
echo [0] 退出
echo.

set /p choice=请选择 (0-8):

if "%choice%"=="1" python main.py run
if "%choice%"=="2" python main.py collect
if "%choice%"=="3" python main.py transcribe
if "%choice%"=="4" python main.py analyze
if "%choice%"=="5" python main.py sync
if "%choice%"=="6" python main.py stats
if "%choice%"=="7" python main.py serve --once
if "%choice%"=="8" python main.py setup-feishu
if "%choice%"=="0" exit

echo.
pause
