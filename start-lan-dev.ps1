$backendDir = "D:\automation-platform\backend"
$frontendDir = "D:\automation-platform\frontend"

$backendCommand = @"
Set-Location '$backendDir'
& '.\.venv\Scripts\Activate.ps1'
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"@

$frontendCommand = @"
Set-Location '$frontendDir'
npm run dev -- --host 0.0.0.0 --port 80
"@

Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand

Write-Host "Started backend and frontend windows."
Write-Host "Frontend: http://127.0.0.1"
Write-Host "Backend: http://127.0.0.1:8000"
