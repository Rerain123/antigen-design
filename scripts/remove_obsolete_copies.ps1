param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$manifestFile = Join-Path $projectRoot 'reports\version-unification-20260927\cleanup-manifest.json'
$manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding utf8 | ConvertFrom-Json
$validated = [Collections.Generic.List[string]]::new()
$checkedParents = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$allowedRoots = @('reports\', 'deploy\', '.tmp\')
foreach ($entry in $manifest.files) {
    $relative = $entry.path.Replace('/', '\')
    if (-not ($allowedRoots | Where-Object { $relative.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })) {
        throw "Outside approved cleanup roots: $relative"
    }
    $target = [IO.Path]::GetFullPath((Join-Path $projectRoot $relative))
    if (-not $target.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or -not $seen.Add($target)) {
        throw 'Unsafe or duplicate target'
    }
    $item = Get-Item -LiteralPath $target -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Not a regular file: $target" }
    $ancestor = $item.Directory
    while ($ancestor -and $ancestor.FullName -ne $projectRoot) {
        if (-not $ancestor.FullName.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Ancestor escaped workspace' }
        if (-not $checkedParents.Add($ancestor.FullName)) { break }
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse ancestor: $($ancestor.FullName)" }
        $ancestor = $ancestor.Parent
    }
    $retained = [IO.Path]::GetFullPath((Join-Path $projectRoot $entry.retained))
    if (-not $retained.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $retained)) { throw 'Retained version missing' }
    if ($item.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) { throw "File changed since inventory: $target" }
    $validated.Add($target)
}
if ($validated.Count -ne $manifest.file_count) { throw 'Manifest count mismatch' }
Write-Output "Validated $($validated.Count) explicit files; $($manifest.bytes) bytes"
if (-not $Apply) { return }
# No recursive deletion: only hash-verified regular files are removed.
foreach ($target in $validated) { Remove-Item -LiteralPath $target -Force }
foreach ($target in $validated) { if (Test-Path -LiteralPath $target) { throw "Deletion incomplete: $target" } }
# Remove only empty parents within the approved roots, never recurse.
foreach ($directory in ($checkedParents | Sort-Object Length -Descending)) {
    if ((Test-Path -LiteralPath $directory) -and -not (Get-ChildItem -LiteralPath $directory -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $directory
    }
}
$receipt = [ordered]@{
    status = 'COMPLETED'
    checked_at = [DateTime]::UtcNow.ToString('o')
    files_deleted = $validated.Count
    bytes_deleted = $manifest.bytes
    manifest_sha256 = (Get-FileHash -LiteralPath $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant()
    cluster_resources_modified = $false
    native_run_data_modified = $false
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'reports\version-unification-20260927\cleanup-receipt.json') -Encoding utf8
$receipt | ConvertTo-Json -Compress
