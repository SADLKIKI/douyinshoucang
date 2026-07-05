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
echo.

set choice=
set /p choice=  请输入选择:

if "%choice%"=="1" goto run
if "%choice%"=="2" goto collect
if "%choice%"=="3" goto transcribe
if "%choice%"=="4" goto fix
if "%choice%"=="5" goto analyze
if "%choice%"=="6" goto sync
if "%choice%"=="7" goto stats
if "%choice%"=="8" goto webui
if "%choice%"=="9" goto serve
if "%choice%"=="0" goto quit

echo.
echo  [!] 无效选择，请重新输入
ping 127.0.0.1 -n 2 >nul
goto menu

:run
python main.py run
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:collect
python main.py collect
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:transcribe
python main.py transcribe
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:fix
python main.py fix-typos
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:analyze
python main.py analyze
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:sync
python main.py sync
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:stats
python main.py stats
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:webui
start http://localhost:8088
python webui.py
goto menu

:serve
python main.py serve --once
echo.
echo  按任意键返回菜单...
pause >nul
goto menu

:quit
exit
