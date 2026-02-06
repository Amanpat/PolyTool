Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
  Write-Output 'Usage: powershell -ExecutionPolicy Bypass -File tools\bootstrap_kb.ps1 [--user <slug>]'
}

function Resolve-UserArg {
  param(
    [string[]]$ArgsList
  )

  $userValue = $null

  for ($i = 0; $i -lt $ArgsList.Count; $i++) {
    $arg = $ArgsList[$i]
    if ($arg -in @('-h', '--help', '/?')) {
      Show-Usage
      exit 0
    }

    if ($arg -in @('--user', '-user', '-u')) {
      if ($i + 1 -ge $ArgsList.Count) {
        Write-Error 'Missing value for --user.'
        exit 1
      }
      $userValue = $ArgsList[$i + 1]
      break
    }
  }

  return $userValue
}

function Format-Path {
  param(
    [string]$Path,
    [string]$RepoRoot
  )

  if ($Path.StartsWith($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $Path.Substring($RepoRoot.Length).TrimStart('\')
  }

  return $Path
}

function Ensure-Dir {
  param(
    [string]$Path,
    [string]$RepoRoot
  )

  $displayPath = Format-Path -Path $Path -RepoRoot $RepoRoot

  if (Test-Path -LiteralPath $Path) {
    Write-Output ("exists: {0}" -f $displayPath)
    return
  }

  New-Item -ItemType Directory -Path $Path | Out-Null
  Write-Output ("created: {0}" -f $displayPath)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$kbRoot = Join-Path $repoRoot 'kb'
$userSlug = Resolve-UserArg -ArgsList $args

Ensure-Dir -Path $kbRoot -RepoRoot $repoRoot
Ensure-Dir -Path (Join-Path $kbRoot 'devlog') -RepoRoot $repoRoot
Ensure-Dir -Path (Join-Path $kbRoot 'specs') -RepoRoot $repoRoot
Ensure-Dir -Path (Join-Path $kbRoot 'users') -RepoRoot $repoRoot

if ($userSlug) {
  $userRoot = Join-Path (Join-Path $kbRoot 'users') $userSlug
  Ensure-Dir -Path $userRoot -RepoRoot $repoRoot
  Ensure-Dir -Path (Join-Path $userRoot 'notes') -RepoRoot $repoRoot
  Ensure-Dir -Path (Join-Path $userRoot 'exports') -RepoRoot $repoRoot
  Ensure-Dir -Path (Join-Path $userRoot 'llm_reports') -RepoRoot $repoRoot
  Ensure-Dir -Path (Join-Path $userRoot 'llm_bundles') -RepoRoot $repoRoot
}

Write-Output 'bootstrap_kb complete.'
