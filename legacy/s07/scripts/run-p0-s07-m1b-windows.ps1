[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^p0-s07-m1b-[A-Za-z0-9-]+$')]
    [string]$CampaignId,

    [ValidatePattern('^[A-Z]:$')]
    [string]$TemporaryDrive = 'P:'
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$driveName = $TemporaryDrive.TrimEnd(':')
$mapped = $false

if (Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue) {
    throw "Temporary drive $TemporaryDrive is already in use; refusing to replace it."
}

try {
    & subst.exe $TemporaryDrive $projectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to map $TemporaryDrive to the workspace."
    }
    $mapped = $true

    $mappedRoot = "$TemporaryDrive\"
    $workspaceRoot = Join-Path $mappedRoot 'legacy\s07'
    $python = Join-Path $mappedRoot '.venv\Scripts\python.exe'
    $runner = Join-Path $workspaceRoot 'scripts\run_p0_s07_m1b.py'
    $blastBin = Join-Path $workspaceRoot 'var\discovery-tools\ncbi-blast-2.17.0\ncbi-blast-2.17.0+\bin'
    $blastDb = Join-Path $workspaceRoot 'var\discovery-data\wwpdb-20260822\blastdb\pdb_seqres_protein'

    & $python $runner `
        --campaign-id $CampaignId `
        --blast-bin $blastBin `
        --blast-db $blastDb
    if ($LASTEXITCODE -ne 0) {
        throw "P0-M1B runner exited with code $LASTEXITCODE."
    }
}
finally {
    if ($mapped) {
        & subst.exe $TemporaryDrive /D
    }
}
