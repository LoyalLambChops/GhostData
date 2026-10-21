@echo off
setlocal
cd /d "%~dp0"
set "GHOSTDATA_ROOT=%~dp0"
if "%GHOSTDATA_ROOT:~-1%"=="\" set "GHOSTDATA_ROOT=%GHOSTDATA_ROOT:~0,-1%"
if not defined GHOSTDATA_PYTHON (
  for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do set "GHOSTDATA_PYTHON=%%P"
)
if not defined GHOSTDATA_PYTHON (
  for /f "usebackq delims=" %%P in (`python -c "import sys; print(sys.executable)" 2^>nul`) do set "GHOSTDATA_PYTHON=%%P"
)
if not defined GHOSTDATA_PYTHON if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  set "GHOSTDATA_PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
if not defined GHOSTDATA_PYTHON (
  echo Python 3.12 or newer was not found.
  exit /b 2
)
set "APP=%~dp0app\GhostData.App\bin\Release\win-x64\GhostData.App.exe"
if not exist "%APP%" (
  echo GhostData has not been built yet. Running Build-GhostData.cmd...
  call "%~dp0Build-GhostData.cmd"
  if errorlevel 1 exit /b %errorlevel%
)
start "GhostData" "%APP%" --root "%GHOSTDATA_ROOT%" --python "%GHOSTDATA_PYTHON%"
endlocal
