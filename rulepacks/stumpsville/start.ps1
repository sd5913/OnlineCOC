param(
    [int]$Port = 8899,
    [string]$Bind = '127.0.0.1',
    [string]$DataDir = '',
    [switch]$NoBrowser,
    [switch]$AI,
    [switch]$P2P,
    [switch]$Web
)
# Keep this file UTF-8 with BOM for Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonPath = Join-Path $projectRoot 'engineering/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先按工程文档准备 Python 运行环境。' }
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$launchArgs = @('-B', (Join-Path $PSScriptRoot 'tools/launch.py'), '--port', $Port, '--bind', $Bind)
if ($DataDir) { $launchArgs += @('--data-dir', $DataDir) }
if ($NoBrowser) { $launchArgs += '--no-browser' }
if ($AI) { $launchArgs += @('--ai-config', (Join-Path $projectRoot 'engineering/ai/config/ai-providers.json')) }
if ($P2P) { $launchArgs += @('--p2p-config', (Join-Path $projectRoot 'engineering/network-p2p/local/client-config.json')) }
if ($Web) { $launchArgs += @('--web-config', (Join-Path $projectRoot 'engineering/network-p2p/local/client-config.json')) }
& $pythonPath @launchArgs
exit $LASTEXITCODE
