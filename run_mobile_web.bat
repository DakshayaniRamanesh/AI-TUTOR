@echo off
echo Starting Kestrel Mobile iOS App in Web / Network Mode...
echo.
echo Network URL: http://192.168.1.7:8550
echo Local URL:   http://localhost:8550
echo.
py -3.12 mobile_app\main.py --web
pause
