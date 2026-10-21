param(
    [switch]$Refresh,
    [string]$Commit = ""
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$SensorRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VendorRoot = Join-Path $SensorRoot "vendor\unityspy"
$SourceRoot = Join-Path $VendorRoot "src"
$Manifest = Join-Path $VendorRoot "manifest.json"
$Repo = "Zero-to-Heroes/unity-spy-.net4.5"
$PinnedCommit = "ac5f555b76dadcbf2a1a0c98bd7de14c0c623ced"

if ((-not $Refresh) -and (Test-Path $Manifest) -and (Test-Path (Join-Path $SourceRoot "UnitySpy")) -and (Test-Path (Join-Path $SourceRoot "UnitySpy.HearthstoneLib"))) {
    $existing = Get-Content $Manifest -Raw | ConvertFrom-Json
    Write-Host "UnitySpy source already prepared."
    Write-Host "  Commit: $($existing.commit)"
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Commit)) { $Commit = $PinnedCommit }
$headers = @{ "User-Agent" = "GhostData-Sensor-Build"; "Accept" = "application/vnd.github+json" }
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ("ghostdata-unityspy-" + [Guid]::NewGuid().ToString("N"))
$zip = Join-Path $temp "unityspy.zip"
$extract = Join-Path $temp "extract"
New-Item -ItemType Directory -Force -Path $extract | Out-Null

try {
    $url = "https://codeload.github.com/$Repo/zip/$Commit"
    Write-Host "Downloading pinned MIT-licensed UnitySpy source..."
    Write-Host "  Commit: $Commit"
    Invoke-WebRequest -Uri $url -OutFile $zip -Headers $headers -UseBasicParsing
    $sha = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    Expand-Archive -Path $zip -DestinationPath $extract -Force
    $repoRoot = Get-ChildItem $extract -Directory | Select-Object -First 1
    if ($null -eq $repoRoot) { throw "Downloaded UnitySpy archive had no repository folder." }
    foreach ($required in @("UnitySpy", "UnitySpy.HearthstoneLib", "LICENSE")) {
        if (-not (Test-Path (Join-Path $repoRoot.FullName $required))) { throw "UnitySpy archive missing: $required" }
    }

    if (Test-Path $SourceRoot) { Remove-Item $SourceRoot -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $SourceRoot | Out-Null
    Copy-Item (Join-Path $repoRoot.FullName "UnitySpy") $SourceRoot -Recurse -Force
    Copy-Item (Join-Path $repoRoot.FullName "UnitySpy.HearthstoneLib") $SourceRoot -Recurse -Force

    $achievementReader = Join-Path $SourceRoot "UnitySpy.HearthstoneLib\Detail\Achievement\AchievementsInfoReader.cs"
    $patches = @()
    if (Test-Path $achievementReader) {
        $sourceText = Get-Content $achievementReader -Raw
        $staleUsing = "    using HackF5.UnitySpy.Crawler;"
        if ($sourceText.Contains($staleUsing)) {
            $sourceText = $sourceText.Replace($staleUsing + "`r`n", "").Replace($staleUsing + "`n", "")
            Set-Content -Path $achievementReader -Value $sourceText -Encoding UTF8
            $patches += "remove_stale_unityspy_crawler_using"
        }
    }

    Copy-Item (Join-Path $repoRoot.FullName "LICENSE") (Join-Path $VendorRoot "LICENSE") -Force
    $payload = [ordered]@{
        repository = "https://github.com/$Repo"
        commit = $Commit
        archive_sha256 = $sha
        license = "MIT"
        compatibility_patches = $patches
        prepared_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $payload | ConvertTo-Json | Set-Content -Path $Manifest -Encoding UTF8
    Write-Host "UnitySpy source prepared."
}
finally {
    if (Test-Path $temp) { Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue }
}
