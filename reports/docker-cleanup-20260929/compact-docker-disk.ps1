$ErrorActionPreference = 'Stop'
$auditRoot = $PSScriptRoot
$diskPath = 'D:\DockerData\DockerDesktopWSL\disk\docker_data.vhdx'
$result = [ordered]@{ disk = $diskPath; started_at = (Get-Date).ToString('o'); success = $false }
try {
    $resolved = (Resolve-Path -LiteralPath $diskPath).Path
    if ($resolved -ne $diskPath) { throw 'Unexpected Docker disk path' }
    $result.before_bytes = (Get-Item -LiteralPath $diskPath).Length
    $handle = [System.IO.File]::Open($diskPath, 'Open', 'Read', 'None')
    $handle.Dispose()
    $commands = @('select vdisk file="D:\DockerData\DockerDesktopWSL\disk\docker_data.vhdx"', 'compact vdisk', 'exit')
    $commandFile = Join-Path $auditRoot 'diskpart-commands.txt'
    $commands | Set-Content -LiteralPath $commandFile -Encoding ASCII
    & "$env:SystemRoot\System32\diskpart.exe" /s $commandFile 2>&1 | Out-File -LiteralPath (Join-Path $auditRoot 'diskpart-output.txt') -Encoding utf8
    $result.exit_code = $LASTEXITCODE
    $result.after_bytes = (Get-Item -LiteralPath $diskPath).Length
    $result.success = ($LASTEXITCODE -eq 0 -and $result.after_bytes -lt $result.before_bytes)
} catch {
    $result.error = $_.Exception.Message
} finally {
    $result.finished_at = (Get-Date).ToString('o')
    $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $auditRoot 'compaction-result.json') -Encoding utf8
}
