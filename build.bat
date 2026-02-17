@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM Build Recorder EXE
REM - Reads VERSION file and prompts for confirmation
REM - Prompts for values
REM - Patches python constants (instead of writing .env):
REM     Recorder\config.py         __version__ = "<VERSION>"
REM     Recorder\config.py         APP_NAME = "<APP_NAME>"
REM     Recorder\utils\lmu.py      BASE_URL = "<LMU_URL>"
REM     Recorder\utils\backend.py  BASE_URL = "<BACKEND_URL>"
REM - Creates/uses Recorder\.venv
REM - Installs requirements.txt (+ pyinstaller)
REM - Ensures icon.ico exists beside this .bat, copies into Recorder
REM - Runs: pyinstaller --onefile --windowed --icon=icon.ico --name "<App Name>" main.py
REM ============================================================

REM ---------- Read and confirm version ----------
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if not exist "%SCRIPT_DIR%\VERSION" (
    echo Error: VERSION file not found: "%SCRIPT_DIR%\VERSION"
    exit /b 1
)

set /p VERSION=<"%SCRIPT_DIR%\VERSION"
set "VERSION=!VERSION: =!"

if "!VERSION!"=="" (
    echo Error: VERSION file is empty.
    exit /b 1
)

echo.
echo ============================================================
echo Building version: !VERSION!
echo ============================================================
echo.
set /p "CONFIRM=Continue with this version? (y/n): "
if /i not "!CONFIRM!"=="y" (
    echo Build cancelled.
    exit /b 0
)

REM ---------- Prompt for values ----------
echo.
set /p "APP_NAME=Application name (APP_NAME): "
if "!APP_NAME!"=="" (
    echo Error: APP_NAME cannot be empty.
    exit /b 1
)

set /p "BACKEND_URL=Backend API URL (BACKEND_URL): "
if "!BACKEND_URL!"=="" (
    echo Error: BACKEND_URL cannot be empty.
    exit /b 1
)

set "DEFAULT_LMU_URL=http://localhost:6397"
set /p "LMU_URL=LMU local API URL [default: %DEFAULT_LMU_URL%]: "
if "!LMU_URL!"=="" set "LMU_URL=%DEFAULT_LMU_URL%"

REM ---------- Resolve directories ----------
set "RECORDER_DIR=%SCRIPT_DIR%\Recorder"

REM ---------- Validate paths ----------
if not exist "%RECORDER_DIR%\" (
    echo Error: Recorder directory not found: "%RECORDER_DIR%"
    exit /b 1
)

if not exist "%SCRIPT_DIR%\icon.ico" (
    echo Error: icon.ico not found next to this script: "%SCRIPT_DIR%\icon.ico"
    exit /b 1
)

if not exist "%RECORDER_DIR%\main.py" (
    echo Error: main.py not found in "%RECORDER_DIR%"
    exit /b 1
)

if not exist "%RECORDER_DIR%\config\settings.py" (
    echo Error: config\settings.py not found in "%RECORDER_DIR%\config"
    exit /b 1
)

if not exist "%RECORDER_DIR%\utils\lmu.py" (
    echo Error: utils\lmu.py not found in "%RECORDER_DIR%\utils"
    exit /b 1
)

if not exist "%RECORDER_DIR%\utils\backend.py" (
    echo Error: utils\backend.py not found in "%RECORDER_DIR%\utils"
    exit /b 1
)

if not exist "%RECORDER_DIR%\requirements.txt" (
    echo Error: requirements.txt not found in "%RECORDER_DIR%"
    exit /b 1
)

REM ---------- Patch Python constants using PowerShell ----------
echo.
echo Patching Python constants...

REM Check if files have already been patched by looking for .bak files
if exist "%RECORDER_DIR%\config\settings.py.bak" (
    echo.
    echo Error: Recorder files appear to already be patched ^(.bak files exist^).
    echo Please revert the Recorder files before running this script again.
    exit /b 1
)

REM Create a temporary PowerShell script
set "PATCH_SCRIPT=%TEMP%\patch_constants_%RANDOM%.ps1"
if exist "%PATCH_SCRIPT%" del /q "%PATCH_SCRIPT%"

>>"%PATCH_SCRIPT%" echo $ErrorActionPreference = 'Stop'
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo function Patch-Constant {
>>"%PATCH_SCRIPT%" echo     param([string]$FilePath, [string]$VarName, [string]$NewValue)
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo     if (-not (Test-Path $FilePath)) { throw "File not found: $FilePath" }
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo     Copy-Item $FilePath "$FilePath.bak" -Force
>>"%PATCH_SCRIPT%" echo     $content = Get-Content $FilePath -Raw
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo     $pattern = '(?m)^(\s*' + [regex]::Escape($VarName) + '\s*=\s*)([''"])(.+?)\2'
>>"%PATCH_SCRIPT%" echo     $replacement = "`$1`${2}$NewValue`${2}"
>>"%PATCH_SCRIPT%" echo     $newContent = [regex]::Replace($content, $pattern, $replacement)
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo     if ($newContent -eq $content) { throw "Could not find $VarName = '...' in $FilePath" }
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo     [System.IO.File]::WriteAllText($FilePath, $newContent)
>>"%PATCH_SCRIPT%" echo     Write-Host "  Patched $VarName in $FilePath"
>>"%PATCH_SCRIPT%" echo }
>>"%PATCH_SCRIPT%" echo.
>>"%PATCH_SCRIPT%" echo Patch-Constant -FilePath '%RECORDER_DIR%\utils\lmu.py' -VarName 'BASE_URL' -NewValue '%LMU_URL%'
>>"%PATCH_SCRIPT%" echo Patch-Constant -FilePath '%RECORDER_DIR%\config\settings.py' -VarName 'APP_NAME' -NewValue '%APP_NAME%'
>>"%PATCH_SCRIPT%" echo Patch-Constant -FilePath '%RECORDER_DIR%\config\settings.py' -VarName '__version__' -NewValue '%VERSION%'
>>"%PATCH_SCRIPT%" echo Patch-Constant -FilePath '%RECORDER_DIR%\utils\backend.py' -VarName 'BASE_URL' -NewValue '%BACKEND_URL%'

powershell -NoProfile -ExecutionPolicy Bypass -File "%PATCH_SCRIPT%"
set "PATCH_RESULT=%ERRORLEVEL%"
del /q "%PATCH_SCRIPT%" 2>nul

if not "%PATCH_RESULT%"=="0" (
    echo.
    echo Error: Failed to patch one or more files. Backups saved as .bak
    echo Please revert the Recorder files before running this script again.
    exit /b 1
)

echo Patching complete.

REM ---------- Embed icon in resources.py ----------
echo.
echo Embedding icon in resources.py...

set "RESOURCES_PY=%RECORDER_DIR%\utils\resources.py"
set "EMBED_SCRIPT=%TEMP%\embed_icon_%RANDOM%.py"

REM Check if already embedded (contains long base64 string, not placeholder)
if exist "%RESOURCES_PY%" (
    findstr /C:"<ICON_BASE64>" "%RESOURCES_PY%" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo Error: Icon appears to already be embedded in resources.py.
        echo Please revert the Recorder files before running this script again.
        exit /b 1
    )
)

REM Create Python script to patch the icon
if exist "%EMBED_SCRIPT%" del /q "%EMBED_SCRIPT%"
>>"%EMBED_SCRIPT%" echo import base64
>>"%EMBED_SCRIPT%" echo import sys
>>"%EMBED_SCRIPT%" echo.
>>"%EMBED_SCRIPT%" echo icon_path = r'%SCRIPT_DIR%\icon.ico'
>>"%EMBED_SCRIPT%" echo resources_path = r'%RESOURCES_PY%'
>>"%EMBED_SCRIPT%" echo.
>>"%EMBED_SCRIPT%" echo try:
>>"%EMBED_SCRIPT%" echo     with open(icon_path, 'rb') as f:
>>"%EMBED_SCRIPT%" echo         icon_bytes = f.read()
>>"%EMBED_SCRIPT%" echo     base64_icon = base64.b64encode(icon_bytes).decode('ascii')
>>"%EMBED_SCRIPT%" echo.
>>"%EMBED_SCRIPT%" echo     with open(resources_path, 'r') as f:
>>"%EMBED_SCRIPT%" echo         content = f.read()
>>"%EMBED_SCRIPT%" echo.
>>"%EMBED_SCRIPT%" echo     if '^<ICON_BASE64^>' not in content:
>>"%EMBED_SCRIPT%" echo         print('Error: Placeholder ^<ICON_BASE64^> not found in resources.py', file=sys.stderr)
>>"%EMBED_SCRIPT%" echo         sys.exit(1)
>>"%EMBED_SCRIPT%" echo.
>>"%EMBED_SCRIPT%" echo     new_content = content.replace('^<ICON_BASE64^>', base64_icon)
>>"%EMBED_SCRIPT%" echo     with open(resources_path, 'w') as f:
>>"%EMBED_SCRIPT%" echo         f.write(new_content)
>>"%EMBED_SCRIPT%" echo     print(f"Embedded icon in: {resources_path}")
>>"%EMBED_SCRIPT%" echo except Exception as e:
>>"%EMBED_SCRIPT%" echo     print(f"Error: {e}", file=sys.stderr)
>>"%EMBED_SCRIPT%" echo     sys.exit(1)

python "%EMBED_SCRIPT%"
set "EMBED_RESULT=%ERRORLEVEL%"
del /q "%EMBED_SCRIPT%" 2>nul

if not "%EMBED_RESULT%"=="0" (
    echo.
    echo Error: Failed to embed icon.
    exit /b 1
)

REM Verify icon was embedded (should no longer contain placeholder)
findstr /C:"<ICON_BASE64>" "%RESOURCES_PY%" >nul 2>&1
if not errorlevel 1 (
    echo.
    echo Error: Icon placeholder still present after embedding.
    exit /b 1
)

echo Icon embedded successfully.

REM ---------- Enter Recorder directory ----------
cd /d "%RECORDER_DIR%" || (
    echo Error: Failed to cd into "%RECORDER_DIR%"
    exit /b 1
)
echo.
echo Working directory: %CD%

REM ---------- Find Python ----------
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if "!PYTHON_CMD!"=="" (
    where py >nul 2>&1 && set "PYTHON_CMD=py"
)

if "!PYTHON_CMD!"=="" (
    echo Error: Python not found in PATH. Install Python and try again.
    exit /b 1
)
echo Using Python: !PYTHON_CMD!

REM ---------- Create virtual environment ----------
if not exist ".venv\" (
    echo.
    echo Creating virtual environment...
    !PYTHON_CMD! -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create virtual environment.
        exit /b 1
    )
) else (
    echo Virtual environment already exists: .venv
)

REM ---------- Activate virtual environment ----------
if not exist ".venv\Scripts\activate.bat" (
    echo Error: venv activation script missing: ".venv\Scripts\activate.bat"
    exit /b 1
)
call ".venv\Scripts\activate.bat"

REM ---------- Install dependencies ----------
echo.
echo Upgrading pip...
python -m pip install --upgrade pip -q
if errorlevel 1 (
    echo Error: Failed to upgrade pip.
    exit /b 1
)

echo Installing requirements...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo Error: Failed to install requirements.txt
    exit /b 1
)

echo Installing PyInstaller...
python -m pip install pyinstaller -q
if errorlevel 1 (
    echo Error: Failed to install pyinstaller
    exit /b 1
)

REM ---------- Copy icon ----------
copy /y "%SCRIPT_DIR%\icon.ico" "%CD%\icon.ico" >nul
if errorlevel 1 (
    echo Error: Failed to copy icon.ico into Recorder.
    exit /b 1
)
echo Copied icon.ico into Recorder directory.

REM ---------- Build with PyInstaller ----------
echo.
echo Building EXE with PyInstaller...
echo   Name: !APP_NAME!
echo   Icon: icon.ico
echo.

pyinstaller --onefile --windowed --icon=icon.ico --add-data "images/setup_session_instructions.jpg;." --name "!APP_NAME!" main.py
if errorlevel 1 (
    echo.
    echo Error: PyInstaller build failed.
    exit /b 1
)

echo.
echo ============================================================
echo Build complete!
echo EXE location: %CD%\dist\!APP_NAME!.exe
echo ============================================================

exit /b 0
