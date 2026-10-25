param([string]$OutputDirectory = '', [string]$BuildPython = 'python')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'dist\GhostData' }
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
if ((Test-Path -LiteralPath $outputRoot) -and (Get-ChildItem -LiteralPath $outputRoot -Force | Select-Object -First 1)) { throw 'Choose an empty output path. Existing builds are never overwritten by packaging.' }
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
Push-Location $projectRoot
try {
    & $BuildPython -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Python regression tests failed.' }
    dotnet build tests/GhostData.ParityHarness/GhostData.ParityHarness.csproj -c Release -m:1 -p:UseSharedCompilation=false
    if ($LASTEXITCODE -ne 0) { throw 'UI regression build failed.' }
    dotnet tests/GhostData.ParityHarness/bin/Release/net10.0/GhostData.ParityHarness.dll
    if ($LASTEXITCODE -ne 0) { throw 'UI regression checks failed.' }
    dotnet publish app/GhostData.App/GhostData.App.csproj -c Release -r win-x64 --self-contained true -o $outputRoot -m:1 -p:UseSharedCompilation=false -p:NuGetAudit=false -p:RuntimeFrameworkVersion=10.0.13
    if ($LASTEXITCODE -ne 0) { throw 'Application publish failed.' }
    & (Join-Path $projectRoot 'sensor\Prepare-UnitySpy.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'UnitySpy preparation failed.' }
    $sensorOutput = Join-Path $outputRoot 'sensor\bin'
    dotnet publish sensor/GhostData.Sensor/GhostData.Sensor.csproj -c Release -o $sensorOutput -m:1 -p:UseSharedCompilation=false -p:NuGetAudit=false
    if ($LASTEXITCODE -ne 0) { throw 'Local sensor publish failed.' }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'sensor\vendor\unityspy\LICENSE') -Destination (Join-Path $sensorOutput 'UnitySpy-LICENSE.txt')
    $pythonZip = Join-Path $outputRoot 'python-runtime.zip'
    # Official published manifest: windows-3.14.8.json, pythonembed-3.14-64.
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.14.8/python-3.14.8-embeddable-amd64.zip' -OutFile $pythonZip -UseBasicParsing
    if ((Get-FileHash -LiteralPath $pythonZip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '80292f0e640e373a54bf09f3b94a1472f976f24a10c5bed0d9622e4e44d67447') { throw 'Python runtime checksum does not match the official release.' }
    $pythonRoot = Join-Path $outputRoot 'python'
    Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonRoot
    Remove-Item -LiteralPath $pythonZip
    Set-Content -LiteralPath (Join-Path $pythonRoot 'python314._pth') -Value @('python314.zip','.','..') -Encoding ASCII
    Copy-Item -LiteralPath (Join-Path $projectRoot 'ghostdata.py') -Destination $outputRoot
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $projectRoot 'ghostdata') -File -Recurse) {
        if ($file.Extension -notin @('.py','.json')) { continue }
        $relative = $file.FullName.Substring($projectRoot.Length+1)
        $target = Join-Path $outputRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target
    }
    New-Item -ItemType Directory -Path (Join-Path $outputRoot 'tools') | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Apply-Update.ps1') -Destination (Join-Path $outputRoot 'tools')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'docs') -Destination $outputRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $projectRoot 'packaging\PORTABLE_README.md') -Destination (Join-Path $outputRoot 'README.md')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'THIRD_PARTY_NOTICES.md') -Destination $outputRoot
    Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination $outputRoot
    foreach ($policy in @('PRIVACY.md','SUPPORT.md','SECURITY.md','CONTRIBUTING.md')) { Copy-Item -LiteralPath (Join-Path $projectRoot $policy) -Destination $outputRoot }
    & $BuildPython -B (Join-Path $PSScriptRoot 'package_notices.py') $projectRoot $outputRoot
    if ($LASTEXITCODE -ne 0) { throw 'Dependency notices could not be collected.' }
    & (Join-Path $pythonRoot 'python.exe') -B (Join-Path $PSScriptRoot 'package_manifest.py') $outputRoot
    if ($LASTEXITCODE -ne 0) { throw 'Package validation failed.' }
    $archive = Join-Path (Split-Path -Parent $outputRoot) 'GhostData-win-x64.zip'
    if (Test-Path -LiteralPath $archive) { throw 'Release archive already exists.' }
    Compress-Archive -Path (Join-Path $outputRoot '*') -DestinationPath $archive -CompressionLevel Optimal
    Get-FileHash -LiteralPath $archive -Algorithm SHA256
} finally { Pop-Location }
