# Kestrel Mobile iOS App Launcher
Write-Host "Launching Kestrel Mobile iOS App (Flet)..." -ForegroundColor Cyan
try {
    py -3.12 mobile_app\main.py
} catch {
    python mobile_app\main.py
}
