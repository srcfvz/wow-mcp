$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

[CmdletBinding()]
param(
  # Optional: pass a specific WoW folder if auto-detect fails.
  # Examples:
  #   "C:\Program Files (x86)\World of Warcraft"
  #   "D:\Games\World of Warcraft\_classic_"
  [string]$WowPath = "",

  # Optional: hint which game folder to prefer when multiple are found.
  # Common values: classic, era, retail.
  [string]$Flavor = ""
)

function Write-Info([string]$Message) { Write-Host $Message }

function Test-AddOnsDir([string]$RootDir) {
  return Test-Path (Join-Path $RootDir "Interface\AddOns")
}

function Get-WowBaseCandidates {
  $candidates = New-Object System.Collections.Generic.List[string]

  if ($WowPath -and (Test-Path $WowPath)) {
    $candidates.Add((Resolve-Path $WowPath).Path)
  }

  $programDirs = @($env:ProgramFiles, $env:"ProgramFiles(x86)") | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique
  $baseNames = @("World of Warcraft", "World of Warcraft Classic")
  foreach ($pd in $programDirs) {
    foreach ($bn in $baseNames) {
      $p = Join-Path $pd $bn
      if (Test-Path $p) { $candidates.Add($p) }
    }
  }

  return $candidates | Select-Object -Unique
}

function Get-InstallTargets([string]$BaseDir) {
  $targets = New-Object System.Collections.Generic.List[string]

  if (Test-AddOnsDir $BaseDir) { $targets.Add($BaseDir) }

  Get-ChildItem -Path $BaseDir -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^_.+_$' } |
    ForEach-Object {
      if (Test-AddOnsDir $_.FullName) { $targets.Add($_.FullName) }
    }

  return $targets
}

function Choose-One([string[]]$Options, [string]$Prompt) {
  if ($Options.Count -le 1) { return $Options[0] }

  Write-Info ""
  Write-Info "Multiple WoW installs found:"
  for ($i = 0; $i -lt $Options.Count; $i++) {
    Write-Info ("[{0}] {1}" -f $i, $Options[$i])
  }

  $raw = Read-Host ($Prompt + " (default 0)")
  if (-not $raw) { return $Options[0] }

  $idx = 0
  if (-not [int]::TryParse($raw, [ref]$idx)) { return $Options[0] }
  if ($idx -lt 0 -or $idx -ge $Options.Count) { return $Options[0] }
  return $Options[$idx]
}

$bundleRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$addonRoot = Join-Path $bundleRoot "addon"
$addonsToInstall = @("WowMCP_State", "WowMCP_Cmd")

foreach ($name in $addonsToInstall) {
  $src = Join-Path $addonRoot $name
  if (-not (Test-Path $src)) {
    throw "Missing addon source folder: $src (run this script from the extracted bundle)"
  }
}

$bases = Get-WowBaseCandidates
$targets = New-Object System.Collections.Generic.List[string]
foreach ($b in $bases) {
  try {
    foreach ($t in (Get-InstallTargets $b)) { $targets.Add($t) }
  } catch {
    # ignore
  }
}

$uniqueTargets = $targets | Select-Object -Unique

if ($Flavor) {
  $needle = $Flavor.ToLowerInvariant()
  $filtered = $uniqueTargets | Where-Object { $_.ToLowerInvariant().Contains($needle) }
  if ($filtered.Count -gt 0) { $uniqueTargets = $filtered }
}

if (-not $uniqueTargets -or $uniqueTargets.Count -eq 0) {
  Write-Info "Could not auto-detect World of Warcraft under Program Files."
  Write-Info "Enter your WoW folder (the one that contains Interface\\ and WTF\\, or a subfolder like _classic_):"
  $manual = Read-Host "WoW path"
  if (-not $manual) { throw "No WoW path provided." }
  if (-not (Test-Path $manual)) { throw "Path does not exist: $manual" }
  $uniqueTargets = @((Resolve-Path $manual).Path)
}

$targetRoot = Choose-One -Options $uniqueTargets -Prompt "Select which install to use"
$addonsDir = Join-Path $targetRoot "Interface\AddOns"

Write-Info ""
Write-Info ("Target AddOns dir: {0}" -f $addonsDir)
Write-Info "Installing addons..."

foreach ($name in $addonsToInstall) {
  $src = Join-Path $addonRoot $name
  $dst = Join-Path $addonsDir $name

  if (Test-Path $dst) {
    Remove-Item -LiteralPath $dst -Recurse -Force
  }
  Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
  Write-Info ("  OK: {0}" -f $name)
}

Write-Info ""
Write-Info "Done."
Write-Info "In WoW: enable 'WowMCP State' (and 'WowMCP Cmd'), then run /reload (SavedVariables flush on reload/logout)."
Write-Info "If addons show 'Out of date', tick 'Load out of date AddOns' (depends on client version)."

