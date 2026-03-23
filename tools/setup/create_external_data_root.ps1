[CmdletBinding()]
param(
  [Parameter()]
  [string]$DataRoot = 'D:\PolyToolData'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-FullPath {
  param(
    [Parameter(Mandatory)]
    [string]$Path
  )

  return [System.IO.Path]::GetFullPath($Path)
}

function Ensure-Directory {
  param(
    [Parameter(Mandatory)]
    [string]$Path,
    [AllowEmptyCollection()]
    [System.Collections.Generic.List[string]]$CreatedPaths,
    [AllowEmptyCollection()]
    [System.Collections.Generic.List[string]]$ExistingPaths
  )

  if (Test-Path -LiteralPath $Path) {
    $item = Get-Item -LiteralPath $Path
    if (-not $item.PSIsContainer) {
      throw ("Required directory path already exists as a file: {0}" -f $Path)
    }

    $ExistingPaths.Add($item.FullName) | Out-Null
    Write-Output ("exists:  {0}" -f $item.FullName)
    return
  }

  $item = New-Item -ItemType Directory -Path $Path
  $CreatedPaths.Add($item.FullName) | Out-Null
  Write-Output ("created: {0}" -f $item.FullName)
}

$resolvedDataRoot = Resolve-FullPath -Path $DataRoot
$createdPaths = [System.Collections.Generic.List[string]]::new()
$existingPaths = [System.Collections.Generic.List[string]]::new()

$directories = @(
  $resolvedDataRoot,
  (Join-Path $resolvedDataRoot 'raw'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker\data'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker\data\polymarket'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker\data\polymarket\trades'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker\data\kalshi'),
  (Join-Path $resolvedDataRoot 'raw\jon_becker\data\kalshi\trades'),
  (Join-Path $resolvedDataRoot 'raw\pmxt_archive'),
  (Join-Path $resolvedDataRoot 'raw\pmxt_archive\Polymarket'),
  (Join-Path $resolvedDataRoot 'raw\pmxt_archive\Kalshi'),
  (Join-Path $resolvedDataRoot 'raw\pmxt_archive\Opinion'),
  (Join-Path $resolvedDataRoot 'raw\price_history_2min'),
  (Join-Path $resolvedDataRoot 'tapes'),
  (Join-Path $resolvedDataRoot 'tapes\polymarket'),
  (Join-Path $resolvedDataRoot 'tapes\kalshi'),
  (Join-Path $resolvedDataRoot 'manifests'),
  (Join-Path $resolvedDataRoot 'logs'),
  (Join-Path $resolvedDataRoot 'rag'),
  (Join-Path $resolvedDataRoot 'rag\polytool_brain')
)

foreach ($directory in $directories) {
  Ensure-Directory -Path $directory -CreatedPaths $createdPaths -ExistingPaths $existingPaths
}

$jonMoveTargetRoot = Join-Path $resolvedDataRoot 'raw\jon_becker'
$pmxtMoveTargetRoot = Join-Path $resolvedDataRoot 'raw\pmxt_archive'
$tapesRoot = Join-Path $resolvedDataRoot 'tapes'
$ragRoot = Join-Path $resolvedDataRoot 'rag\polytool_brain'

Write-Output ''
Write-Output 'External PolyTool data root is ready.'
Write-Output ("Data root:             {0}" -f $resolvedDataRoot)
Write-Output ("Jon move target root:  {0}" -f $jonMoveTargetRoot)
Write-Output ("pmxt move target root: {0}" -f $pmxtMoveTargetRoot)
Write-Output ("tapes root:            {0}" -f $tapesRoot)
Write-Output ("rag root:              {0}" -f $ragRoot)
Write-Output ("Created directories:   {0}" -f $createdPaths.Count)
Write-Output ("Existing directories:  {0}" -f $existingPaths.Count)
