@echo off
setlocal

REM Build single-file EXE (framework-dependent, no runtime bundled).
REM Requires: .NET SDK 8.x installed.

set SCRIPT_DIR=%~dp0
set OUT_DIR=%SCRIPT_DIR%dist

REM Close running app to avoid "file is being used" during publish.
taskkill /IM VNTextractor.exe /F >nul 2>nul

echo [1/2] Publish...
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
dotnet publish "%SCRIPT_DIR%src\VNTextractor.WinForms\VNTextractor.WinForms.csproj" ^
  -c Release ^
  -r win-x64 ^
  --self-contained false ^
  -o "%OUT_DIR%"
if errorlevel 1 goto :fail

echo [2/2] Done: "%OUT_DIR%\VNTextractor.exe"
exit /b 0

:fail
echo Build failed.
exit /b 1
