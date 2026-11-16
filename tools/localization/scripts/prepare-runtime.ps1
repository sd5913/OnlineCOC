$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
if ((node --version) -ne 'v24.22.1') { throw 'Developer build requires Node 24.22.1.' }
New-Item -ItemType Directory -Path '.cache' -Force | Out-Null
$env:electron_config_cache = Join-Path (Get-Location) '.cache/electron'
node node_modules/electron/install.js
if ($LASTEXITCODE -ne 0) { throw 'Electron runtime download failed' }
Invoke-WebRequest -Uri 'https://nodejs.org/dist/v24.22.1/SHASUMS256.txt' -OutFile '.cache/node-shasums.txt'
Invoke-WebRequest -Uri 'https://nodejs.org/dist/v24.22.1/node-v24.22.1-win-x64.zip' -OutFile '.cache/node-v24.22.1-win-x64.zip'
$expected = ((Get-Content -LiteralPath '.cache/node-shasums.txt' | Where-Object { $_ -match ' node-v24.22.1-win-x64.zip$' }) -split '\s+')[0]
$actual = (Get-FileHash -LiteralPath '.cache/node-v24.22.1-win-x64.zip' -Algorithm SHA256).Hash.ToLower()
if ($expected -ne $actual) { throw 'Node archive checksum mismatch' }
Expand-Archive -LiteralPath '.cache/node-v24.22.1-win-x64.zip' -DestinationPath '.cache' -Force
Write-Output "Node archive verified: $actual"
