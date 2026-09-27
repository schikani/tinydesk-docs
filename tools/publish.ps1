# publish.ps1 - copy the site to the web server from Windows (OpenSSH's scp,
# included in Windows 10 and 11).
#
#   .\tools\publish.ps1 -Server me@myserver -Dest /var/www/tinydesk
#
# scp copies everything and deletes nothing; files you removed from site\
# stay on the server until you delete them there (or use publish.sh from WSL,
# which mirrors with rsync).
param(
    [Parameter(Mandatory = $true)][string]$Server,
    [string]$Dest = "/var/www/tinydesk"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
python (Join-Path $root "tools\check_links.py")
if ($LASTEXITCODE -ne 0) { throw "check_links.py failed" }
ssh $Server "mkdir -p '$Dest'"
scp -r (Join-Path $root "site\*") "${Server}:$Dest/"
Write-Host "published to ${Server}:$Dest"
