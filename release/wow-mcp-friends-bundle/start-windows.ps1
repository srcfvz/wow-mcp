$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Err([string]$Message) { Write-Host $Message -ForegroundColor Red }

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content -LiteralPath $Path | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    if ($line.StartsWith("#")) { return }

    $m = [regex]::Match($line, '^(?<key>[A-Za-z_][A-Za-z0-9_]*)=(?<val>.*)$')
    if (-not $m.Success) { return }

    $key = $m.Groups["key"].Value
    $val = $m.Groups["val"].Value.Trim()
    if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
      $val = $val.Substring(1, $val.Length - 2)
    }
    Set-Item -Path ("Env:{0}" -f $key) -Value $val
  }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $scriptDir ".env"
Import-DotEnv $envFile

if (-not $env:WOW_SAVEDVARS_DIR_HOST) {
  Write-Err "ERROR: WOW_SAVEDVARS_DIR_HOST is not set."
  Write-Err "Create a .env next to this script (copy .env.example) and set WOW_SAVEDVARS_DIR_HOST."
  exit 2
}

if (-not $env:WOW_SCAN_ROOT_HOST) {
  $env:WOW_SCAN_ROOT_HOST = $env:WOW_SAVEDVARS_DIR_HOST
}

$image = "wow-mcp:local"
& docker image inspect $image *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Err "ERROR: Docker image not built yet."
  Write-Err "Run: docker compose build wow-mcp"
  exit 2
}

$stateFile = if ($env:WOW_STATE_FILE) { $env:WOW_STATE_FILE } else { "WowMCP_State.lua" }
$stateVar = if ($env:WOW_STATE_VAR) { $env:WOW_STATE_VAR } else { "WowMCP_State" }
$cmdFile = if ($env:WOW_CMD_FILE) { $env:WOW_CMD_FILE } else { "WowMCP_Cmd.lua" }
$cmdVar = if ($env:WOW_CMD_VAR) { $env:WOW_CMD_VAR } else { "WowMCP_Cmd" }
$probeMaxDepth = if ($env:WOW_PROBE_MAX_DEPTH) { $env:WOW_PROBE_MAX_DEPTH } else { "9" }

& docker run --rm -i --network none `
  -v "$($env:WOW_SAVEDVARS_DIR_HOST):/wow/SavedVariables:rw" `
  -v "$($env:WOW_SCAN_ROOT_HOST):/wow/scan:ro" `
  -e WOW_SAVEDVARS_DIR="/wow/SavedVariables" `
  -e WOW_STATE_FILE="$stateFile" `
  -e WOW_STATE_VAR="$stateVar" `
  -e WOW_CMD_FILE="$cmdFile" `
  -e WOW_CMD_VAR="$cmdVar" `
  -e WOW_SCAN_ROOT="/wow/scan" `
  -e WOW_PROBE_MAX_DEPTH="$probeMaxDepth" `
  $image

