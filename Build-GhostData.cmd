@echo off
setlocal
cd /d "%~dp0"
set "GHOSTDATA_DOTNET=dotnet"
if exist "%~dp0.dotnet\dotnet.exe" set "GHOSTDATA_DOTNET=%~dp0.dotnet\dotnet.exe"
if not exist "%~dp0.dotnet\dotnet.exe" (
  where dotnet >nul 2>nul
  if errorlevel 1 (
    echo GhostData requires the Microsoft .NET 10 SDK.
    exit /b 2
  )
)
echo.
echo [1/3] Building selected-deck sensor...
call "%~dp0sensor\Build-Sensor.cmd"
if errorlevel 1 exit /b %errorlevel%
echo.
echo [2/3] Building GhostData dashboard...
"%GHOSTDATA_DOTNET%" publish "%~dp0app\GhostData.App\GhostData.App.csproj" -c Release -r win-x64 --self-contained false -o "%~dp0app\GhostData.App\bin\Release\win-x64" -m:1 -p:NuGetAudit=false -p:UseSharedCompilation=false
if errorlevel 1 exit /b %errorlevel%
echo.
if defined GHOSTDATA_SKIP_LAUNCHER goto launcher_done
echo [3/3] Building double-click launcher...
"%GHOSTDATA_DOTNET%" build "%~dp0launcher\GhostData.Launcher.csproj" -c Release -m:1 -p:NuGetAudit=false
if errorlevel 1 exit /b %errorlevel%
copy /y "%~dp0launcher\bin\Release\net48\GhostData-Verify-Build-Launch.exe" "%~dp0GhostData-Verify-Build-Launch.exe" >nul
:launcher_done
echo.
echo GhostData build complete.
endlocal
