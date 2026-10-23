param(
    [string]$PackageDirectory = '',
    [string]$Compiler = '',
    [string]$OutputDirectory = '',
    [string]$AppId = '',
    [string]$DisplayName = 'GhostData'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $PackageDirectory) { $PackageDirectory = Join-Path $projectRoot 'dist\GhostData' }
$packageRoot = (Resolve-Path -LiteralPath $PackageDirectory).Path
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'dist' }
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $Compiler) {
    $candidates = @((Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'))
    $Compiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $Compiler -or -not (Test-Path -LiteralPath $Compiler)) { throw 'Install the official Inno Setup compiler or pass -Compiler. This is a maintainer-only tool.' }
$identity = Get-Content -LiteralPath (Join-Path $packageRoot 'ghostdata-release.json') -Raw | ConvertFrom-Json
$expected = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
if ($identity.product -ne 'GhostData' -or $identity.version -ne $expected) { throw 'Build the current portable package first.' }
& (Join-Path $packageRoot 'python\python.exe') -B (Join-Path $packageRoot 'ghostdata.py') --verify-release $packageRoot
if ($LASTEXITCODE -ne 0) { throw 'Portable payload integrity check failed.' }
$arguments = @('/Qp',('/DAppVersion='+$expected),('/DPayloadDir='+$packageRoot),('/DOutputDir='+$outputRoot),('/DDisplayName='+$DisplayName))
if ($AppId) {
    $parsed = [Guid]::Parse($AppId)
    $arguments += '/DAppIdValue={' + $parsed.ToString().ToUpperInvariant() + '}'
}
& $Compiler @arguments (Join-Path $projectRoot 'packaging\GhostData.iss')
if ($LASTEXITCODE -ne 0) { throw 'Windows installer compilation failed.' }
$artifact = Join-Path $outputRoot ('GhostData-Setup-'+$expected+'-x64.exe')
$hash = Get-FileHash -LiteralPath $artifact -Algorithm SHA256
$identityId = '{1C35DA89-E657-4DD0-AEAA-EE63E6745D23}'
if ($AppId) { $identityId = '{' + ([Guid]::Parse($AppId)).ToString().ToUpperInvariant() + '}' }
# This local build receipt lets the destructive integration test reject a
# production installer before it executes. It is not a signature/trust claim.
@{ product='GhostData'; version=$expected; app_id=$identityId; display_name=$DisplayName; sha256=$hash.Hash } |
    ConvertTo-Json | Set-Content -LiteralPath ($artifact + '.build.json') -Encoding UTF8
$hash
