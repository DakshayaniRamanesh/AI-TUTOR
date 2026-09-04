@echo off
echo Starting Kestrel Mobile iOS App on Local Network...
echo.
echo You can open this on your iPhone, iPad, or any phone on the same Wi-Fi!
echo Network URL: http://192.168.1.7:8550
echo Local URL:   http://localhost:8550
echo.
py -u -3.12 mobile_app\main.py --network
pause
