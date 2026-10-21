@echo off
setlocal
cd /d "%~dp0"
if not defined GHOSTDATA_DOTNET set "GHOSTDATA_DOTNET=dotnet"
if exist "%~dp0..\.dotnet\dotnet.exe" set "GHOSTDATA_DOTNET=%~dp0..\.dotnet\dotnet.exe"
where pwsh >nul 2>nul
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-UnitySpy.ps1"
) else (
  pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-UnitySpy.ps1"
)
if errorlevel 1 exit /b %errorlevel%
if not exist bin mkdir bin
if exist bin\GhostData.Sensor.exe del /q bin\GhostData.Sensor.exe >nul 2>nul
echo Building GhostData.Sensor...
"%GHOSTDATA_DOTNET%" publish "%~dp0GhostData.Sensor\GhostData.Sensor.csproj" -c Release -o "%~dp0bin" -m:1 -p:NuGetAudit=false
if errorlevel 1 exit /b %errorlevel%
copy /y "%~dp0vendor\unityspy\manifest.json" "%~dp0bin\unityspy-manifest.json" >nul
copy /y "%~dp0vendor\unityspy\LICENSE" "%~dp0bin\UNITYSPY_LICENSE.txt" >nul
echo GhostData.Sensor built successfully.
"%~dp0bin\GhostData.Sensor.exe" health --json
endlocal
