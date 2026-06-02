param(
    [string]$Provider = "openrouter",
    [string]$Version = "v3",
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Missing .venv. Run start_web_ui.ps1 once or create the virtual environment first."
}

& $Python -m pip install -r (Join-Path $Root "requirements.txt")
& $Python -c "import openai, pydantic_core, jiter, requests, yaml" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Repairing native provider dependencies for this Python version..."
    & $Python -m pip install --force-reinstall --no-cache-dir --timeout 180 pydantic-core==2.46.4 jiter==0.15.0
}

$ArgsList = @("telegram_bot.py", "--provider", $Provider, "--version", $Version)
if ($Model.Trim()) {
    $ArgsList += @("--model", $Model)
}

& $Python $ArgsList
