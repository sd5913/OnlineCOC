param([string]$Config = "$PSScriptRoot/local/host.json")
$ErrorActionPreference = 'Stop'
$moduleRoot = $PSScriptRoot
$python = Join-Path $moduleRoot '../network-p2p/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { & (Join-Path $moduleRoot '../network-p2p/setup.ps1') }
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $python -c 'import onlinecoc_web' 2>$null
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install --no-deps -e $moduleRoot
    if ($LASTEXITCODE -ne 0) { throw '网页模块安装失败' }
}
if (-not (Test-Path -LiteralPath $Config)) {
    throw '请先运行 scripts/configure_host.py 生成 local/host.json，或指定 -Config。详见本目录 README.md。'
}
Write-Host '网页联机启动后，在 local/room/web-entry.json 中查看房间代号与房主认领码。Ctrl+C 只关闭网页联机适配器。'
& $python -m onlinecoc_web host --config $Config
