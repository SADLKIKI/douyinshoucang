@echo off
chcp 65001 >nul
title DOUYlike
cd /d "%~dp0"

:menu
cls
echo.
echo  ============================================
echo   DOUYlike - 抖音收藏夹自动更新系统
echo  ============================================
echo.
echo   [1] 执行完整流水线
echo   [2] 仅采集收藏夹
echo   [3] 仅转写逐字稿
echo   [4] AI 纠错逐字稿
echo   [5] 仅 AI 分析
echo   [6] 仅同步飞书
echo   [7] 查看统计信息
echo   [8] 启动 Web 控制台
echo   [9] 启动定时任务
echo   [0] 退出
echo.
echo  ============================================

set /p choice=  请选择:

if "%choice%"=="1" goto run
if "%choice%"=="2" goto collect
if "%choice%"=="3" goto transcribe
if "%choice%"=="4" goto fix
if "%choice%"=="5" goto analyze
if "%choice%"=="6" goto sync
if "%choice%"=="7" goto stats
if "%choice%"=="8" goto webui
if "%choice%"=="9" goto serve
if "%choice%"=="0" exit

echo.
echo  [!] 无效选项
timeout /t 2 >nul
goto menu

:run
echo.
echo  >> 执行完整流水线...
python main.py run
echo.
pause
goto menu

:collect
echo.
echo  >> 采集收藏夹...
python main.py collect
echo.
pause
goto menu

:transcribe
echo.
echo  >> 转写逐字稿...
python main.py transcribe
echo.
pause
goto menu

:fix
echo.
echo  >> AI 纠错逐字稿...
python main.py fix-typos
echo.
pause
goto menu

:analyze
echo.
echo  >> AI 分析...
python main.py analyze
echo.
pause
goto menu

:sync
echo.
echo  >> 同步飞书...
python main.py sync
echo.
pause
goto menu

:stats
echo.
python main.py stats
echo.
pause
goto menu

:webui
echo.
echo  >> 启动 Web 控制台...
echo  >> 浏览器打开 http://localhost:8088
start http://localhost:8088
python webui.py
goto menu

:serve
echo.
echo  >> 启动定时任务...
python main.py serve --once
echo.
pause
goto menu
