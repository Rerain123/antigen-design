param(
    [string]$Workspace = (Split-Path -Parent $PSScriptRoot),
    [string]$CampaignId = "p0-s07-task6-acceptance-20260903-c",
    [string]$DriveLetter = "P:"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$workspacePath = (Resolve-Path -LiteralPath $Workspace).Path
$workspaceRelative = [IO.Path]::GetRelativePath($projectRoot, $workspacePath)
if ($workspaceRelative -eq '..' -or $workspaceRelative.StartsWith("..\")) {
    throw "Workspace must remain inside the T-01 project root."
}
$drivePrefix = [regex]::Escape("$DriveLetter\")
$existing = (& subst.exe) | Where-Object { $_ -match "^$drivePrefix" }
if ($existing) {
    throw "$DriveLetter is already assigned; choose a free drive letter."
}

try {
    & subst.exe $DriveLetter $projectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to map $DriveLetter to the workspace."
    }
    $mappedWorkspace = Join-Path "$DriveLetter\" $workspaceRelative
    $python = Join-Path $DriveLetter ".venv\Scripts\python.exe"
    $runner = Join-Path $mappedWorkspace "scripts\run_s07_task6_acceptance.py"
    if (-not (Test-Path -LiteralPath $python)) {
        throw "Python runtime was not found through the temporary ASCII drive mapping."
    }
    & $python $runner --workspace $mappedWorkspace --campaign-id $CampaignId
    if ($LASTEXITCODE -ne 0) {
        throw "Task 6 acceptance runner failed with exit code $LASTEXITCODE."
    }
}
finally {
    & subst.exe $DriveLetter /D 2>$null
}
