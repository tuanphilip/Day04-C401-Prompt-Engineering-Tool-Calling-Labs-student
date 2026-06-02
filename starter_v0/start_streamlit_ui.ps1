param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Missing .venv. Create it first with: python -m venv .venv"
}

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python -c "import openai, pydantic_core, jiter, streamlit" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Repairing native provider dependencies for this Python version..."
    & $Python -m pip install --force-reinstall --no-cache-dir --timeout 180 pydantic-core==2.46.4 jiter==0.15.0
}

$Url = "http://${HostName}:$Port"
Start-Process $Url
& $Python -m streamlit run (Join-Path $Root "app.py") --server.address $HostName --server.port $Port
