# Shared Windows x64 runtime for AI Manager and Stumpsville (PowerShell 5.1+).
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$ArchivePath,
    [string]$WheelDirectory,
    [switch]$Offline,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$root = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
function Inside([string]$relative) {
    if ([IO.Path]::IsPathRooted($relative)) { throw 'Expected a project-relative path.' }
    $path = [IO.Path]::GetFullPath((Join-Path $root $relative))
    if (!$path.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes project.' }
    return $path
}
function RunPython([string]$exe, [string[]]$arguments) {
    & $exe @arguments
    if ($LASTEXITCODE -ne 0) { throw ('Python step failed (exit ' + $LASTEXITCODE + '). See the log, correct the cause and rerun setup-game.cmd.') }
}
function FileHash([string]$path) {
    $sha = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
$guard = $null
$transcript = $false
try {
    if (![Environment]::Is64BitProcess) { throw 'Windows x64 PowerShell is required.' }
    $config = Get-Content -LiteralPath (Inside 'launcher-config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.schemaVersion -ne 1 -or $config.python.version -notmatch '^3\.14\.\d+$' -or $config.python.sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw 'Unsupported Python configuration.' }
    $lock = Inside $config.dependencies.lockFile
    $runtime = Inside $config.python.directory
    $basePython = Join-Path $runtime 'python.exe'
    $venv = Inside 'engineering/.venv'
    $python = Join-Path $venv 'Scripts/python.exe'
    $marker = Join-Path $venv 'onlinecoc-game-ready.txt'
    $mutex = Inside 'engineering/.runtime/desktop-tools.lock'
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($mutex)) | Out-Null
    try { $guard = [IO.File]::Open($mutex, 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Another installer or desktop host is running. Close it and retry.' }
    $logs = Inside 'engineering/.runtime/game-setup-logs'
    [IO.Directory]::CreateDirectory($logs) | Out-Null
    $log = Join-Path $logs ((Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID + '.log')
    Start-Transcript -LiteralPath $log | Out-Null
    $transcript = $true
    $probe = "import sys,struct,tkinter; assert '.'.join(map(str,sys.version_info[:3])) == '$($config.python.version)' and struct.calcsize('P') == 8; r=tkinter.Tk(); r.withdraw(); print('PYTHON_TK_OK',sys.version.split()[0],r.tk.call('info','patchlevel')); r.destroy()"
    if (!$VerifyOnly) {
        if (!(Test-Path -LiteralPath $basePython)) {
            if (Test-Path -LiteralPath $runtime) { throw 'Incomplete Python directory. Preserve the log and move that directory aside before retrying.' }
            if (!$ArchivePath) { $ArchivePath = Inside $config.python.cacheFile }
            if (!(Test-Path -LiteralPath $ArchivePath)) {
                if ($Offline) { throw 'Offline mode requires the hash-verified full Python archive.' }
                $url = [Uri]$config.python.archiveUrl
                if ($url.Scheme -ne 'https' -or $url.UserInfo) { throw 'Python download requires HTTPS without embedded credentials.' }
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($ArchivePath))) | Out-Null
                $partial = $ArchivePath + '.' + [Guid]::NewGuid().ToString('N') + '.partial'
                [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
                Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $partial
                if ((FileHash $partial) -ne $config.python.sha256) { throw 'Python download hash mismatch; archive not executed.' }
                Move-Item -LiteralPath $partial -Destination $ArchivePath
            }
            if ((FileHash $ArchivePath) -ne $config.python.sha256) { throw 'Python archive hash mismatch; archive not executed.' }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $staging = $runtime + '.extracting-' + [Guid]::NewGuid().ToString('N')
            [IO.Directory]::CreateDirectory($staging) | Out-Null
            $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($ArchivePath))
            try {
                foreach ($entry in $zip.Entries) {
                    $destination = [IO.Path]::GetFullPath((Join-Path $staging $entry.FullName))
                    if (!$destination.StartsWith($staging + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path escapes extraction directory.' }
                    if (!$entry.Name) { [IO.Directory]::CreateDirectory($destination) | Out-Null }
                    else {
                        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
                        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination)
                    }
                }
            } finally { $zip.Dispose() }
            RunPython (Join-Path $staging 'python.exe') @('-I','-c',$probe)
            # Both absolute paths were derived under this project's runtime root.
            [IO.Directory]::Move($staging, $runtime)
        }
        RunPython $basePython @('-I','-c',$probe)
        if (!(Test-Path -LiteralPath $python)) {
            if (Test-Path -LiteralPath $venv) { throw 'Incomplete .venv directory. Preserve it and move it aside before retrying.' }
            RunPython $basePython @('-I','-m','venv',$venv)
        }
        RunPython $python @('-I','-c',$probe)
        if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker }
        $arguments = @('-I','-m','pip','--isolated','install','--disable-pip-version-check','--require-hashes','--only-binary=:all:','-r',$lock)
        if ($Offline) { $arguments += '--no-index' }
        else {
            $index = [Uri]$config.dependencies.indexUrl
            if ($index.Scheme -ne 'https' -or $index.UserInfo) { throw 'Package index requires HTTPS without embedded credentials.' }
            $arguments += @('--index-url',$index.AbsoluteUri)
        }
        if (!$WheelDirectory) { $WheelDirectory = Inside $config.dependencies.wheelDirectory }
        if (Test-Path -LiteralPath $WheelDirectory) { $arguments += @('--find-links',[IO.Path]::GetFullPath($WheelDirectory)) }
        RunPython $python $arguments
    }
    if (!(Test-Path -LiteralPath $python)) { throw 'Shared .venv is missing. Run engineering/setup-game.cmd first.' }
    RunPython $python @('-I','-c',$probe)
    RunPython $python @('-I','-c',"import fastapi,uvicorn,httpx,jsonschema,pwdlib,argon2,websockets,lupa.lua54; print('RUNTIME_IMPORTS_OK')")
    RunPython $python @('-I','-m','pip','check')
    if (!$VerifyOnly) { [IO.File]::WriteAllText($marker, (FileHash $lock)) }
    Write-Host 'GAME_RUNTIME_READY: engineering/.venv (AI Manager + Stumpsville).'
    Write-Host ('Log: ' + $log)
} catch {
    Write-Host ('SETUP_FAILED: ' + $_.Exception.Message)
    if ($log) { Write-Host ('Log: ' + $log) }
    exit 1
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($guard) { $guard.Dispose() }
}
