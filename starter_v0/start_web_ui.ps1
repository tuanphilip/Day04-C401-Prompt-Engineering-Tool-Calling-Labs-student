param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8501
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $Root "start_streamlit_ui.ps1") -HostName $HostName -Port $Port
