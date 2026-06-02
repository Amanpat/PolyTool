#Requires -Version 5.1
<#
.SYNOPSIS
    Registers Windows Scheduled Tasks for Obsidian vault sync scripts.

.DESCRIPTION
    Idempotent — safe to run multiple times. Each call unregisters the task if it
    already exists, then re-registers it fresh so the trigger/action stays current.

    Tasks registered:
        VaultSync-RepoDocs   — runs sync-repo-docs.py every 15 minutes
        VaultSync-RisMirror  — runs sync-ris-mirror.py every 5 minutes

    Both tasks run as the current user, with the repo root as working directory,
    and append stdout/stderr to files under docs/obsidian-vault/.sync-logs/.

.NOTES
    Run this script once as the current user (no elevation required for
    current-user tasks). Task Scheduler stores the tasks under
    \VaultSync-RepoDocs and \VaultSync-RisMirror in the root folder.

    To verify after registration:
        Get-ScheduledTask -TaskName VaultSync-RepoDocs
        Get-ScheduledTask -TaskName VaultSync-RisMirror

    To remove:
        Unregister-ScheduledTask -TaskName VaultSync-RepoDocs -Confirm:$false
        Unregister-ScheduledTask -TaskName VaultSync-RisMirror -Confirm:$false
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Script lives at <repo>/docs/scripts/ — repo root is two levels up.
$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$SyncLogsDir = Join-Path $RepoRoot 'docs\obsidian-vault\.sync-logs'

# Ensure output directory exists before tasks first fire.
if (-not (Test-Path $SyncLogsDir)) {
    New-Item -ItemType Directory -Path $SyncLogsDir -Force | Out-Null
    Write-Host "Created: $SyncLogsDir"
}

# ---------------------------------------------------------------------------
# Helper — register one task (idempotent)
# ---------------------------------------------------------------------------

function Register-VaultSyncTask {
    param(
        [string] $TaskName,
        [string] $ScriptPath,      # Absolute path to the .py script
        [string] $LogFile,         # Absolute path to the .log file
        [int]    $IntervalMinutes
    )

    # Remove existing task silently so we get a clean re-register.
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed existing task: $TaskName"
    }

    # Build the PowerShell command that the task will execute.
    # It sets the working directory, runs the script, and appends output to the log file.
    $PsCommand = @"
Set-Location '$RepoRoot'; python '$ScriptPath' >> '$LogFile' 2>&1
"@

    $Action = New-ScheduledTaskAction `
        -Execute 'powershell.exe' `
        -Argument "-NonInteractive -WindowStyle Hidden -Command `"$PsCommand`""

    # Trigger: start once (1 min from now) then repeat indefinitely.
    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

    # Settings: allow task to run on battery, no time limit.
    $Settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
        -MultipleInstances IgnoreNew `
        -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action   $Action `
        -Trigger  $Trigger `
        -Settings $Settings `
        -RunLevel Limited `
        -Force | Out-Null

    Write-Host "Registered: $TaskName  (every $IntervalMinutes min)"
    Write-Host "  Script : $ScriptPath"
    Write-Host "  Log    : $LogFile"
}

# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

$Tasks = @(
    @{
        TaskName        = 'VaultSync-RepoDocs'
        ScriptPath      = Join-Path $RepoRoot 'docs\scripts\sync-repo-docs.py'
        LogFile         = Join-Path $SyncLogsDir 'sync-repo-docs.log'
        IntervalMinutes = 15
    },
    @{
        TaskName        = 'VaultSync-RisMirror'
        ScriptPath      = Join-Path $RepoRoot 'docs\scripts\sync-ris-mirror.py'
        LogFile         = Join-Path $SyncLogsDir 'sync-ris-mirror.log'
        IntervalMinutes = 5
    }
)

foreach ($t in $Tasks) {
    Register-VaultSyncTask `
        -TaskName        $t.TaskName `
        -ScriptPath      $t.ScriptPath `
        -LogFile         $t.LogFile `
        -IntervalMinutes $t.IntervalMinutes
}

Write-Host ''
Write-Host 'Done. Both tasks are registered and will fire within the next minute.'
Write-Host 'Verify with: Get-ScheduledTask -TaskName VaultSync-*'
