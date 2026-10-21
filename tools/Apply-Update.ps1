param([Parameter(Mandatory=$true)][string]$PlanPath)
$ErrorActionPreference = 'Stop'
$plan = Get-Content -LiteralPath $PlanPath -Raw | ConvertFrom-Json
$installRoot = [IO.Path]::GetFullPath($plan.root).TrimEnd('\')
$stagedRoot = [IO.Path]::GetFullPath($plan.staged).TrimEnd('\')
$parentRoot = [IO.Path]::GetDirectoryName($installRoot)
$previousRoot = Join-Path $parentRoot ('.ghostdata-previous-' + [Guid]::NewGuid().ToString('N'))
$failedRoot = Join-Path $parentRoot ('.ghostdata-failed-' + [Guid]::NewGuid().ToString('N'))
$logPath = Join-Path (Split-Path -Parent $PlanPath) 'install.log'
try {
    # Every move/delete target is an absolute sibling of the exact installation.
    foreach ($candidate in @($stagedRoot,$previousRoot,$failedRoot)) {
        if ([IO.Path]::GetDirectoryName($candidate) -ne $parentRoot -or $candidate -eq $installRoot) { throw 'Invalid update boundary.' }
    }
    if ((Split-Path -Leaf $stagedRoot) -notlike '.ghostdata-update-*' -or (Test-Path -LiteralPath (Join-Path $installRoot '.git'))) { throw 'Source checkouts cannot be replaced.' }
    foreach ($candidate in @($installRoot,$stagedRoot)) {
        if ((Get-Item -LiteralPath $candidate).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installations cannot be replaced.' }
        $identity = Get-Content -LiteralPath (Join-Path $candidate 'ghostdata-release.json') -Raw | ConvertFrom-Json
        if ($identity.product -ne 'GhostData') { throw 'Incorrect package identity.' }
    }
    # Wait for orderly UI/recorder shutdown; never terminate the user's old app.
    $parentProcess = Get-Process -Id $plan.parent_pid -ErrorAction SilentlyContinue
    if ($parentProcess -and -not $parentProcess.WaitForExit(120000)) { throw 'GhostData did not close; installation deferred.' }
    & (Join-Path $installRoot 'python\python.exe') -B (Join-Path $installRoot 'ghostdata.py') --verify-release $installRoot
    if ($LASTEXITCODE -ne 0) { throw 'Installation changed or contains user files; update cancelled.' }
    $checker = Join-Path $stagedRoot 'python\python.exe'
    & $checker -B (Join-Path $stagedRoot 'ghostdata.py') --verify-release $stagedRoot
    if ($LASTEXITCODE -ne 0) { throw 'Staged package verification failed.' }
    Move-Item -LiteralPath $installRoot -Destination $previousRoot
    try { Move-Item -LiteralPath $stagedRoot -Destination $installRoot }
    catch { Move-Item -LiteralPath $previousRoot -Destination $installRoot; throw }
    $ack = Join-Path (Split-Path -Parent $PlanPath) 'started.txt'
    try {
        # The UI is explicitly restarted as part of the user's requested update.
        $newProcess = Start-Process -FilePath (Join-Path $installRoot 'GhostData.App.exe') -ArgumentList @('--update-ack',('"'+$ack+'"')) -WorkingDirectory $installRoot -WindowStyle Hidden -PassThru
        $deadline = [DateTime]::UtcNow.AddSeconds(60)
        while (-not (Test-Path -LiteralPath $ack) -and -not $newProcess.HasExited -and [DateTime]::UtcNow -lt $deadline) { Start-Sleep -Milliseconds 200 }
        if (-not (Test-Path -LiteralPath $ack)) { throw 'New application did not acknowledge startup.' }
    } catch {
        if ($newProcess -and -not $newProcess.HasExited) { $newProcess.Kill(); $newProcess.WaitForExit() }
        Move-Item -LiteralPath $installRoot -Destination $failedRoot
        Move-Item -LiteralPath $previousRoot -Destination $installRoot
        Start-Process -FilePath (Join-Path $installRoot 'GhostData.App.exe') -WorkingDirectory $installRoot -WindowStyle Hidden
        throw
    }
    if ([IO.Path]::GetDirectoryName($previousRoot) -eq $parentRoot -and (Split-Path -Leaf $previousRoot) -like '.ghostdata-previous-*') {
        Remove-Item -LiteralPath $previousRoot -Recurse -Force
    }
    'Update installed successfully.' | Set-Content -LiteralPath $logPath
} catch {
    $_.Exception.Message | Set-Content -LiteralPath $logPath
    exit 1
}
