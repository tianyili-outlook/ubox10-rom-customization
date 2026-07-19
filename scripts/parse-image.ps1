# scripts/parse-image.ps1
# Automates the extraction of partition manifest and verification of checksums

$ErrorActionPreference = 'Stop'
$ImagePath = 'x12-1024.img'
$ManifestPath = 'work/manifest.json'

Write-Host "============================================="
Write-Host "Starting M1: Parsing and Verifying Firmware..."
Write-Host "============================================="

# 1. Verify baseline
Write-Host "[1/3] Verifying original firmware baseline..."
& .\scripts\verify-baseline.ps1 -ImagePath $ImagePath

# 2. Extract partition manifest
Write-Host "[2/3] Extracting partition manifest to $ManifestPath ..."
python tools/sunxi_image_tool.py list $ImagePath --json $ManifestPath

# 3. Verify partition checksums
Write-Host "[3/3] Verifying partition checksums..."
python tools/sunxi_image_tool.py verify $ImagePath

Write-Host "`n[SUCCESS] M1 parsing and verification complete!"
