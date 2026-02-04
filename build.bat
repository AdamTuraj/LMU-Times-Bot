@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM Build Recorder EXE
REM - Prompts for values
REM - Patches python constants (instead of writing .env):
REM     Recorder\utils\lmu.py      BASE_URL = "<LMU_URL>"
REM     Recorder\main.py           APP_NAME = "<APP_NAME>"
REM     Recorder\utils\backend.py  BASE_URL = "<BACKEND_URL>"
REM - Creates/uses Recorder\.venv
REM - Installs requirements.txt (+ pyinstaller)
REM - Ensures icon.ico exists beside this .bat, copies into Recorder
REM - Runs: pyinstaller --onefile --windowed --icon=icon.ico --name "<App Name>" main.py
REM ============================================================

REM ---------- Prompt for values ----------
set /p APP_NAME=Application name (APP_NAME): 
if "%APP_NAME%"=="" (
  echo Error: APP_NAME cannot be empty.
  exit /b 1
)

set /p BACKEND_URL=Backend API URL (used to set utils/backend.py BASE_URL): 
if "%BACKEND_URL%"=="" (
  echo Error: BACKEND_URL cannot be empty.
  exit /b 1
)

set "DEFAULT_LMU_URL=http://localhost:6397"
set /p LMU_URL=LMU local API URL (used to set utils/lmu.py BASE_URL) [default: %DEFAULT_LMU_URL%]: 
if "%LMU_URL%"=="" set "LMU_URL=%DEFAULT_LMU_URL%"

REM ---------- Resolve script directory ----------
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM ---------- Validate paths ----------
if not exist "%SCRIPT_DIR%\Recorder\" (
  echo Error: Recorder directory not found: "%SCRIPT_DIR%\Recorder\"
  exit /b 1
)

if not exist "%SCRIPT_DIR%\icon.ico" (
  echo Error: icon.ico not found next to this script: "%SCRIPT_DIR%\icon.ico"
  exit /b 1
)

REM ---------- Enter Recorder ----------
cd /d "%SCRIPT_DIR%\Recorder" || (
  echo Error: Failed to cd into "%SCRIPT_DIR%\Recorder"
  exit /b 1
)
echo Working directory: %CD%

REM ---------- Ensure target files exist ----------
if not exist "%CD%\main.py" (
  echo Error: main.py not found in "%CD%"
  exit /b 1
)
if not exist "%CD%\utils\lmu.py" (
  echo Error: utils\lmu.py not found in "%CD%\utils"
  exit /b 1
)
if not exist "%CD%\utils\backend.py" (
  echo Error: utils\backend.py not found in "%CD%\utils"
  exit /b 1
)

REM ---------- Patch python constants (with backups) ----------
echo.
echo Patching Python constants...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "function Patch($path,$pattern,$replacement) {" ^
  "  if(!(Test-Path $path)) { throw 'Missing file: ' + $path }" ^
  "  Copy-Item $path ($path + '.bak') -Force;" ^
  "  $c = Get-Content $path -Raw;" ^
  "  $n = [regex]::Replace($c, $pattern, $replacement, 'Multiline');" ^
  "  if($n -eq $c) { throw ('No change made (pattern not found): ' + $path) }" ^
  "  Set-Content -LiteralPath $path -Value $n -NoNewline;" ^
  "}" ^
  "$lmu = Join-Path $PWD 'utils\lmu.py';" ^
  "$main = Join-Path $PWD 'main.py';" ^
  "$backend = Join-Path $PWD 'utils\backend.py';" ^
  "Patch $lmu '^(\\s*BASE_URL\\s*=\\s*)(''[^\r\n]*''|\"\"[^\r\n]*\"\"|\"[^\r\n]*\"|''[^\r\n]*'')' ('$1\"%LMU_URL%\"');" ^
  "Patch $main '^(\\s*APP_NAME\\s*=\\s*)(''[^\r\n]*''|\"\"[^\r\n]*\"\"|\"[^\r\n]*\"|''[^\r\n]*'')' ('$1\"%APP_NAME%\"');" ^
  "Patch $backend '^(\\s*BASE_URL\\s*=\\s*)(''[^\r\n]*''|\"\"[^\r\n]*\"\"|\"[^\r\n]*\"|''[^\r\n]*'')' ('$1\"%BACKEND_URL%\"');"

if errorlevel 1 (
  echo.
  echo Error: Failed to patch one or more files.
  echo (Backups saved as .bak next to each file.)
  exit /b 1
)

echo Patched:
echo   utils\lmu.py      BASE_URL = "%LMU_URL%"
echo   main.py           APP_NAME  = "%APP_NAME%"
echo   utils\backend.py  BASE_URL = "%BACKEND_URL%"

REM ---------- Find Python ----------
set "PYTHON_LAUNCHER="
where python >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_LAUNCHER=python"
) else (
  where py >nul 2>&1
  if not errorlevel 1 set "PYTHON_LAUNCHER=py"
)

if "%PYTHON_LAUNCHER%"=="" (
  echo Error: Python not found in PATH. Install Python and try again.
  exit /b 1
)
echo Using Python launcher: %PYTHON_LAUNCHER%

REM ---------- Create venv ----------
if not exist ".venv\" (
  echo Creating virtual environment...
  %PYTHON_LAUNCHER% -m venv .venv
  if errorlevel 1 (
    echo Error: Failed to create virtual environment.
    exit /b 1
  )
) else (
  echo Virtual environment already exists: .venv
)

REM ---------- Activate venv ----------
if not exist ".venv\Scripts\activate.bat" (
  echo Error: venv activation script missing: ".venv\Scripts\activate.bat"
  exit /b 1
)
call ".venv\Scripts\activate.bat"

REM ---------- Install deps ----------
if not exist "requirements.txt" (
  echo Error: requirements.txt not found in "%CD%"
  exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
  echo Error: Failed to upgrade pip.
  exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Error: Failed to install requirements.txt
  exit /b 1
)

python -m pip install pyinstaller
if errorlevel 1 (
  echo Error: Failed to install pyinstaller
  exit /b 1
)

REM ---------- Copy icon into Recorder (keep original beside .bat) ----------
copy /y "%SCRIPT_DIR%\icon.ico" "%CD%\icon.ico" >nul
if errorlevel 1 (
  echo Error: Failed to copy icon.ico into Recorder.
  exit /b 1
)
echo Copied icon.ico into Recorder directory.

REM ---------- Build with PyInstaller ----------
echo.
echo Building EXE with PyInstaller...
pyinstaller --onefile --windowed --icon=icon.ico --name "%APP_NAME%" main.py
if errorlevel 1 (
  echo Error: PyInstaller build failed.
  exit /b 1
)

echo.
echo Done!
echo EXE output: "%CD%\dist\%APP_NAME%.exe"
exit /b 0
