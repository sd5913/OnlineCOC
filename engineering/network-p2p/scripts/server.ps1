param([string]$Command,[string]$UploadLocal,[string]$RemotePath)
$ErrorActionPreference='Stop'
$moduleRoot=Split-Path $PSScriptRoot -Parent
$server=Get-Content -Raw -LiteralPath (Join-Path $moduleRoot 'local/server.json') | ConvertFrom-Json
$keyPath=Join-Path $moduleRoot $server.keyFile
$knownHostsPath=(Join-Path $moduleRoot 'local/ssh-known-hosts').Replace('\','/')
$options=@('-F','none','-i',$keyPath,'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','PreferredAuthentications=publickey','-o','PasswordAuthentication=no','-o','KbdInteractiveAuthentication=no','-o','ConnectTimeout=10','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-o','StrictHostKeyChecking=yes','-o',('UserKnownHostsFile="'+$knownHostsPath+'"'),'-o','GlobalKnownHostsFile=NUL')
$destination=$server.user+'@'+$server.host
if($UploadLocal){
    if($RemotePath -notmatch '^/[-a-zA-Z0-9_./]+$'){throw 'Invalid remote path'}
    & scp @options -P $server.port $UploadLocal ($destination+':'+$RemotePath)
}else{
    & ssh @options -p $server.port $destination $Command
}
if($LASTEXITCODE -ne 0){throw "SSH/SCP failed ($LASTEXITCODE)"}
