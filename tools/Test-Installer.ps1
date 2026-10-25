param([Parameter(Mandatory=$true)][string]$Installer)
$ErrorActionPreference = 'Stop'
$Installer = (Resolve-Path -LiteralPath $Installer).Path
$receipt = Get-Content -LiteralPath ($Installer + '.build.json') -Raw | ConvertFrom-Json
if ($receipt.product -ne 'GhostData' -or $receipt.app_id -ne '{E10FD240-677C-4875-8744-711F6B2A2136}' -or
    $receipt.display_name -ne 'GhostData Packaging Test' -or $receipt.sha256 -ne (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash) {
    throw 'Refusing to execute: build a separate test installer with the documented test identity.'
}
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$expectedVersion = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
$testParent = Join-Path $projectRoot 'test-temp'
$testRoot = Join-Path $testParent ('installer-' + [Guid]::NewGuid().ToString('N'))
$installation = Join-Path $testRoot 'App with spaces'
$payload = Join-Path $installation 'app'
$data = Join-Path $testRoot 'data'
$regKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{E10FD240-677C-4875-8744-711F6B2A2136}_is1'
$shortcutName = 'GhostData Packaging Test.lnk'
$links = @((Join-Path ([Environment]::GetFolderPath('Desktop')) $shortcutName),
    (Join-Path ([Environment]::GetFolderPath('Programs')) $shortcutName))
if ((Test-Path -LiteralPath $regKey) -or ($links | Where-Object { Test-Path -LiteralPath $_ })) { throw 'Test identity already exists; preserve it.' }
New-Item -ItemType Directory -Path $testRoot,$data -Force | Out-Null
$sentinel = Join-Path $data 'history-preservation.txt'
Set-Content -LiteralPath $sentinel -Value 'Keep my match history' -Encoding ASCII
$sentinelHash = (Get-FileHash -LiteralPath $sentinel).Hash
# Upgrade/recovery tests model a user who completed first-run setup.
# First-run UI is validated separately; do not leave a modal blocking shutdown.
@{schema_version=1;game_directory='';setup_seen=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $data 'settings.json') -Encoding UTF8
$previousData = $env:GHOSTDATA_DATA_DIR
$env:GHOSTDATA_DATA_DIR = $data
function Run-Checked([string]$File, [string[]]$Arguments) {
    $p = Start-Process -FilePath $File -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if (-not $p.WaitForExit(60000)) { throw ('Test process timeout: ' + $File) }
    if ($p.ExitCode -ne 0) { throw ('Test process failed: ' + $File + ' exit ' + $p.ExitCode) }
}
function Verify-Payload {
    & (Join-Path $payload 'python\python.exe') -B (Join-Path $payload 'ghostdata.py') --verify-release $payload
    if ($LASTEXITCODE -ne 0) { throw 'Installed payload did not verify.' }
}
function Close-TestApp {
    foreach ($process in Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'GhostData.App.exe' -and $_.ExecutablePath -eq (Join-Path $payload 'GhostData.App.exe') }) {
        $p = Get-Process -Id $process.ProcessId
        $deadline = [DateTime]::UtcNow.AddSeconds(20)
        while (-not $p.HasExited -and $p.MainWindowHandle -eq [IntPtr]::Zero -and [DateTime]::UtcNow -lt $deadline) {
            Start-Sleep -Milliseconds 200; $p.Refresh()
        }
        if (-not $p.HasExited -and (-not $p.CloseMainWindow() -or -not $p.WaitForExit(15000))) { throw 'Test app failed orderly shutdown.' }
    }
}
function Update-PackageManifest([string]$Root) {
    & (Join-Path $Root 'python\python.exe') -B (Join-Path $PSScriptRoot 'package_manifest.py') $Root
    if ($LASTEXITCODE -ne 0) { throw 'Test fixture manifest failed.' }
}
try {
    $setupArgs = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="'+$installation+'"'),'/TASKS=desktopicon',('/LOG="'+(Join-Path $testRoot 'setup.log')+'"'))
    Run-Checked $Installer $setupArgs
    if (-not (Test-Path -LiteralPath $regKey)) { throw 'Wrong installer identity: compile with the test AppId and DisplayName.' }
    Verify-Payload
    $shell = New-Object -ComObject WScript.Shell
    foreach ($path in $links) {
        if (-not (Test-Path -LiteralPath $path)) { throw 'Shortcut missing.' }
        $link = $shell.CreateShortcut($path)
        if ($link.TargetPath -ne (Join-Path $payload 'GhostData.App.exe') -or $link.IconLocation -notlike '*GhostData.App.exe*') { throw 'Shortcut target or icon is wrong.' }
    }
    'PASS: install, payload integrity, Start Menu and Desktop shortcuts'
    $runtime = Get-Content -LiteralPath (Join-Path $payload 'GhostData.App.runtimeconfig.json') -Raw | ConvertFrom-Json
    if ($runtime.runtimeOptions.tfm -ne 'net10.0') { throw 'Unexpected .NET target.' }
    $preview = Join-Path $testRoot 'preview'; New-Item -ItemType Directory -Path $preview | Out-Null
    Copy-Item -Path (Join-Path $projectRoot 'tests\fixtures\preview\*.json') -Destination $preview
    Run-Checked (Join-Path $payload 'GhostData.App.exe') @('--preview',('"'+$preview+'"'),'--preview-exit')
    $checks = Get-Content -LiteralPath (Join-Path $preview 'validation.json') -Raw | ConvertFrom-Json
    if (-not $checks.readableNames -or -not $checks.scrolls -or -not $checks.hoverHitTest -or -not $checks.textOnly) { throw 'Installed preview regression.' }
    'PASS: installed .NET 10 UI and rail render'
    # Model an obsolete file from a verified earlier package; Setup must replace
    # the entire payload rather than retaining old runtime/code files.
    Set-Content -LiteralPath (Join-Path $payload 'obsolete-test-file.txt') -Value 'old payload'
    Update-PackageManifest $payload
    Run-Checked $Installer $setupArgs
    Verify-Payload
    if (Test-Path -LiteralPath (Join-Path $payload 'obsolete-test-file.txt')) { throw 'Upgrade retained obsolete payload files.' }
    if (Test-Path -LiteralPath (Join-Path $installation '.previous-package')) { throw 'Upgrade retained its temporary predecessor.' }
    'PASS: reinstall/upgrade replaces obsolete files'
    $maintenance = Join-Path $installation 'maintenance'
    $maintenanceHashes = @(Get-ChildItem -LiteralPath $maintenance -File | Get-FileHash | ForEach-Object { $_.Hash }) -join ','
    $originalExeHash = (Get-FileHash -LiteralPath (Join-Path $payload 'GhostData.App.exe')).Hash
    foreach ($scenario in @('failure','success')) {
        $stage = Join-Path $installation ('.ghostdata-update-' + [Guid]::NewGuid().ToString('N'))
        Copy-Item -LiteralPath $payload -Destination $stage -Recurse
        if ($scenario -eq 'failure') {
            # Signed Windows utility exits immediately on --update-ack; models
            # a verified candidate whose UI fails before startup acknowledgement.
            Copy-Item -LiteralPath (Join-Path $env:WINDIR 'System32\where.exe') -Destination (Join-Path $stage 'GhostData.App.exe') -Force
        }
        Update-PackageManifest $stage
        $helperDir = Join-Path $testRoot $scenario; New-Item -ItemType Directory -Path $helperDir | Out-Null
        $helper = Join-Path $helperDir 'Apply-Update.ps1'; Copy-Item -LiteralPath (Join-Path $payload 'tools\Apply-Update.ps1') -Destination $helper
        $plan = Join-Path $helperDir 'plan.json'
        @{root=$payload;staged=$stage;parent_pid=2147483647} | ConvertTo-Json | Set-Content -LiteralPath $plan -Encoding UTF8
        $process = Start-Process -FilePath (Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',('"'+$helper+'"'),'-PlanPath',('"'+$plan+'"')) -WindowStyle Hidden -PassThru
        if (-not $process.WaitForExit(60000)) { throw 'Update helper timed out.' }
        if (($scenario -eq 'success' -and $process.ExitCode -ne 0) -or ($scenario -eq 'failure' -and $process.ExitCode -eq 0)) { throw ('Unexpected update result: ' + $scenario) }
        Close-TestApp
        Verify-Payload
        if ((Get-FileHash -LiteralPath (Join-Path $payload 'GhostData.App.exe')).Hash -ne $originalExeHash) { throw 'Update/rollback altered the expected application.' }
        $after = @(Get-ChildItem -LiteralPath $maintenance -File | Get-FileHash | ForEach-Object { $_.Hash }) -join ','
        if ($after -ne $maintenanceHashes) { throw 'Update altered uninstall files.' }
        if (-not (Test-Path -LiteralPath (Join-Path $installation 'ghostdata-install.json'))) { throw 'Update lost installer identity.' }
        ('PASS: ' + $scenario + ' update preserves installed metadata and original app')
    }
    if ((Get-ItemProperty -LiteralPath $regKey).DisplayVersion -ne $expectedVersion) { throw 'Installed version label is wrong.' }
    Run-Checked (Join-Path $maintenance 'unins000.exe') @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART')
    if ((Test-Path -LiteralPath $payload) -or (Test-Path -LiteralPath $regKey) -or ($links | Where-Object { Test-Path -LiteralPath $_ })) { throw 'Uninstall left app, registration or shortcuts behind.' }
    if ((Get-FileHash -LiteralPath $sentinel).Hash -ne $sentinelHash) { throw 'User data was changed.' }
    'PASS: uninstall removes app/shortcuts and preserves user data'
    ('Evidence: ' + $testRoot)
} finally {
    $env:GHOSTDATA_DATA_DIR = $previousData
}
