@echo off
title DOUYlike
cd /d "%~dp0"

:menu
cls
echo.
echo  ============================================
echo   DOUYlike
echo  ============================================
echo.
echo   [1] Run full pipeline
echo   [2] Collect favorites
echo   [3] Transcribe videos
echo   [4] AI fix typos
echo   [5] AI analyze
echo   [6] Sync to Feishu
echo   [7] Show stats
echo   [8] Start Web UI
echo   [9] Run once (scheduled)
echo   [0] Exit
echo.
echo  ============================================
echo.

set choice=
set /p choice=  Select:

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

echo Invalid choice
ping 127.0.0.1 -n 2 >nul
goto menu

:run
python main.py run
echo.
pause
goto menu

:collect
python main.py collect
echo.
pause
goto menu

:transcribe
python main.py transcribe
echo.
pause
goto menu

:fix
python main.py fix-typos
echo.
pause
goto menu

:analyze
python main.py analyze
echo.
pause
goto menu

:sync
python main.py sync
echo.
pause
goto menu

:stats
python main.py stats
echo.
pause
goto menu

:webui
start http://localhost:8088
python webui.py
goto menu

:serve
python main.py serve --once
echo.
pause
goto menu

:quit
exit
