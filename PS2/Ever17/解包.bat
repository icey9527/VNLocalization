@echo off
setlocal enabledelayedexpansion

set "tool_dir=%~dp0"
set "tool=%tool_dir%Kid.exe"
set "source_folder=%~1"
set "output_base=%~2"

if not defined source_folder set "source_folder=input"
if not defined output_base set "output_base=extracted"

if not exist "%tool%" (
    echo tool not found: %tool%
    exit /b 1
)

if not exist "%source_folder%" (
    echo source folder not found: %source_folder%
    exit /b 1
)

set "file_count=0"
set "single_count=0"

for %%f in ("%source_folder%\*.afs") do (
    if exist "%%f" (
        set /a file_count+=1
        set "output_dir=%output_base%\%%~nf"
        "%tool%" u "%%~f" "!output_dir!"
    )
)

for %%f in ("%source_folder%\*") do (
    if exist "%%f" (
        if /I not "%%~xf"==".afs" (
            if not exist "%%~ff\" (
                set /a single_count+=1
                set "output_file=%output_base%\%%~nxf"
                "%tool%" d "%%~f" "!output_file!"
            )
        )
    )
)
