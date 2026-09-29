@echo off
rem ============================================================
rem  kita 构建脚本：发布单文件 exe（games\*.ini 随发布复制到 exe 旁）
rem  依赖本机 .NET 8 运行时；运行时 ini 从 exe 目录读取。
rem ============================================================
cd /d "%~dp0"

dotnet publish -c Release -r win-x64
if errorlevel 1 (
    echo.
    echo [ERROR] kita publish failed.
    pause
    exit /b 1
)

echo.
echo [OK] %~dp0bin\Release\net8.0-windows\win-x64\publish\kita.exe
pause
