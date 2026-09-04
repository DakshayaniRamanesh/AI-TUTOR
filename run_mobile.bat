@echo off
echo Starting Kestrel Mobile iOS App (Flet)...
py -3.12 mobile_app\main.py
if %ERRORLEVEL% NEQ 0 (
    python mobile_app\main.py
)
pause
