[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("politics", "sports", "new_market", "unknown")]
    [string]$Regime,

    [Parameter()]
    [ValidateSet("politics", "sports", "new_market", "unknown")]
    [string]$TargetRegime,

    [Parameter()]
    [string]$SourceManifest = "artifacts/gates/gate2_tape_manifest.json",

    [Parameter()]
    [ValidateRange(1, 100)]
    [int]$ScanTop = 20,

    [Parameter()]
    [ValidateRange(1, 20)]
    [int]$PackTop = 3,

    [Parameter()]
    [ValidateRange(1.0, 86400.0)]
    [double]$DurationSeconds = 600,

    [Parameter()]
    [ValidateRange(1.0, 3600.0)]
    [double]$PollIntervalSeconds = 30,

    [Parameter()]
    [ValidateRange(0.01, 2.0)]
    [double]$NearEdge = 1.0,

    [Parameter()]
    [ValidateRange(1.0, 100000.0)]
    [double]$MinDepth = 50,

    [Parameter()]
    [string]$TapesBaseDir = "artifacts/simtrader/tapes"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$pythonRelative = ".\.venv\Scripts\python.exe"
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$sessionPacksDir = Join-Path $repoRoot "artifacts\session_packs"
$rankedOutDir = Join-Path $repoRoot "artifacts\watchlists"
$runStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$rankedJsonRelative = "artifacts/watchlists/gate2_ranked_$runStamp.json"

function Resolve-ProjectPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PathValue))
}

function Quote-CommandPart {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch "[\s'`"]") {
        return $Value
    }

    return "'" + ($Value -replace "'", "''") + "'"
}

function Format-CommandLine {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $parts = @($Executable) + $Arguments
    return ($parts | ForEach-Object { Quote-CommandPart -Value $_ }) -join " "
}

function Format-ProcessArgumentList {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    return ($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        }
        else {
            $_
        }
    }) -join " "
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $display = Format-CommandLine -Executable $pythonRelative -Arguments $Arguments
    Write-Host "[$Label] $display"
    & $pythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path $pythonExe)) {
    throw "Python interpreter not found: $pythonExe"
}

$resolvedSourceManifest = Resolve-ProjectPath -PathValue $SourceManifest
if (-not (Test-Path $resolvedSourceManifest -PathType Leaf)) {
    throw "Source manifest not found: $SourceManifest"
}

if ($PackTop -gt $ScanTop) {
    throw "-PackTop cannot be greater than -ScanTop."
}

New-Item -ItemType Directory -Path $rankedOutDir -Force | Out-Null
New-Item -ItemType Directory -Path $sessionPacksDir -Force | Out-Null

$scanArgs = @(
    "-m", "polytool", "scan-gate2-candidates",
    "--all",
    "--top", $ScanTop.ToString(),
    "--enrich",
    "--ranked-json-out", $rankedJsonRelative
)

$packArgs = @(
    "-m", "polytool", "make-session-pack",
    "--ranked-json", $rankedJsonRelative,
    "--top", $PackTop.ToString(),
    "--regime", $Regime,
    "--source-manifest", $SourceManifest,
    "--duration", $DurationSeconds.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
    "--poll-interval", $PollIntervalSeconds.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
    "--near-edge", $NearEdge.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
    "--min-depth", $MinDepth.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture)
)

if ($PSBoundParameters.ContainsKey("TargetRegime")) {
    $packArgs += @("--target-regime", $TargetRegime)
}

Push-Location $repoRoot
try {
    Invoke-CheckedCommand -Label "scan-gate2" -Arguments $scanArgs
    Invoke-CheckedCommand -Label "make-session-pack" -Arguments $packArgs

    $sessionPack = Get-ChildItem $sessionPacksDir -Directory |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1

    if ($null -eq $sessionPack) {
        throw "No session pack was created under artifacts/session_packs."
    }

    $sessionPlanPath = Join-Path $sessionPack.FullName "session_plan.json"
    if (-not (Test-Path $sessionPlanPath -PathType Leaf)) {
        throw "Newest session pack is missing session_plan.json: $sessionPlanPath"
    }

    $stdoutLog = Join-Path $sessionPack.FullName "watch_stdout.log"
    $stderrLog = Join-Path $sessionPack.FullName "watch_stderr.log"

    $watchArgs = @(
        "-m", "polytool", "watch-arb-candidates",
        "--watchlist-file", $sessionPlanPath,
        "--regime", $Regime,
        "--duration", $DurationSeconds.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
        "--poll-interval", $PollIntervalSeconds.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
        "--near-edge", $NearEdge.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
        "--min-depth", $MinDepth.ToString("0.###", [System.Globalization.CultureInfo]::InvariantCulture),
        "--tapes-base-dir", $TapesBaseDir
    )

    $watchProcess = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList (Format-ProcessArgumentList -Arguments $watchArgs) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru

    $tapeManifestCommand = Format-CommandLine -Executable $pythonRelative -Arguments @(
        "-m", "polytool", "tape-manifest",
        "--tapes-dir", $TapesBaseDir,
        "--out", $SourceManifest
    )
    $preflightCommand = Format-CommandLine -Executable $pythonRelative -Arguments @(
        "-m", "polytool", "gate2-preflight",
        "--tapes-dir", $TapesBaseDir
    )

    Write-Host ""
    Write-Host "Background watcher launched."
    Write-Host "  PID          : $($watchProcess.Id)"
    Write-Host "  Session pack : $($sessionPack.FullName)"
    Write-Host "  Session plan : $sessionPlanPath"
    Write-Host "  Stdout log   : $stdoutLog"
    Write-Host "  Stderr log   : $stderrLog"
    Write-Host ""
    Write-Host "Follow-up commands:"
    Write-Host "  $tapeManifestCommand"
    Write-Host "  $preflightCommand"
}
finally {
    Pop-Location
}
