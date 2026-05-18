@echo off
setlocal enabledelayedexpansion

set "tool_dir=%~dp0"
set "tool=%tool_dir%Kid.exe"
set "source_folder=%~1"
set "output_folder=%~2"

if not defined source_folder set "source_folder=new"
if not defined output_folder set "output_folder=packed"

if not exist "%tool%" (
    echo tool not found: %tool%
    exit /b 1
)

if not exist "%source_folder%" (
    echo source folder not found: %source_folder%
    exit /b 1
)

set "folder_count=0"
set "file_count=0"

for /d %%d in ("%source_folder%\*") do (
    set /a folder_count+=1
    set "output_file=%output_folder%\%%~nxd.afs"
    "%tool%" p "%%~fd" "!output_file!"
)

for %%f in ("%source_folder%\*") do (
    if exist "%%f" (
        if /I not "%%~xf"==".afs" if /I not "%%~nxf"=="list.xml" (
            if not exist "%%~ff\" (
                set /a file_count+=1
                set "output_file=%output_folder%\%%~nxf"
                "%tool%" c "%%~ff" "!output_file!"
            )
        )
    )
)
