[CmdletBinding()]
param(
    [string]$ImagePath = 'x12-1024.img',
    [string]$ExpectedSha256 = '371A653604618E8B78786F279EA6F64E5D1028B430C9B41F330B08456A264065'
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
    throw "找不到固件：$ImagePath"
}

$resolvedImagePath = (Resolve-Path -LiteralPath $ImagePath).Path
$actual = (Get-FileHash -LiteralPath $resolvedImagePath -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actual -ne $ExpectedSha256) {
    throw "固件 SHA-256 不匹配。期望：$ExpectedSha256；实际：$actual"
}

Write-Output "基线验证成功：$actual"
