param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Missing .venv. Create it first, then install requirements.txt."
}

$CloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($CloudflaredCommand) {
    $Cloudflared = $CloudflaredCommand.Source
} else {
    $Cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
}

if (-not (Test-Path $Cloudflared)) {
    throw "Missing cloudflared. Install with: winget install --id Cloudflare.cloudflared"
}

Write-Host "Starting Streamlit UI on http://${HostName}:$Port ..."
$UiProcess = Start-Process `
    -FilePath $Python `
    -ArgumentList @("-m", "streamlit", "run", "app.py", "--server.address", $HostName, "--server.port", "$Port", "--server.headless", "true") `
    -WorkingDirectory $Root `
    -PassThru

try {
    Start-Sleep -Seconds 8
    Write-Host ""
    Write-Host "Opening Cloudflare Tunnel. Copy the https://*.trycloudflare.com URL into REPORT.md Part A."
    Write-Host "Keep this terminal open while other teams test the UI."
    Write-Host ""
    & $Cloudflared tunnel --url "http://${HostName}:$Port" --no-autoupdate
}
finally {
    if ($UiProcess -and -not $UiProcess.HasExited) {
        Stop-Process -Id $UiProcess.Id -Force
    }
}
