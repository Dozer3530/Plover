# Builds plover-vX.Y.Z.zip for the QGIS plugin manager / GitHub Releases.
# Includes runtime files only (no tests, no caches). Run from the repo root.
#
# Entries are written with forward slashes explicitly: Compress-Archive would
# use backslashes, which breaks extraction on Linux/macOS.

$ErrorActionPreference = "Stop"

$metadata = Get-Content "$PSScriptRoot\tsp_route_generator\metadata.txt"
$version = ($metadata | Select-String '^version=(.+)$').Matches[0].Groups[1].Value.Trim()
$zipPath = Join-Path $PSScriptRoot "plover-v$version.zip"

$runtimeFiles = @(
    "__init__.py",
    "metadata.txt",
    "LICENSE",
    "icon.png",
    "tsp_route_generator.py",
    "tsp_route_generator_dialog.py",
    "route_task.py",
    "geometry_utils.py",
    "tsp_core.py",
    "processing_provider.py"
)

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, "Create")
try {
    foreach ($file in $runtimeFiles) {
        $source = Join-Path "$PSScriptRoot\tsp_route_generator" $file
        if (-not (Test-Path $source)) { throw "Missing runtime file: $source" }
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $zip, $source, "tsp_route_generator/$file") | Out-Null
    }
} finally {
    $zip.Dispose()
}

Write-Host "Built plover-v$version.zip ($([math]::Round((Get-Item $zipPath).Length / 1KB, 1)) KB)"
Write-Host "Attach it to a GitHub Release; it is gitignored on purpose."
