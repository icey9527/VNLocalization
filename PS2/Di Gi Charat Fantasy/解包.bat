@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo          AFS文件批量解压工具
echo ========================================

:: 设置AFS文件所在文件夹
set "source_folder=.\input_afs"
:: 设置输出文件夹
set "output_base=.\extracted"

:: 创建输出文件夹
if not exist "%output_base%" mkdir "%output_base%"

:: 检查源文件夹是否存在
if not exist "%source_folder%" (
    echo 错误：源文件夹 %source_folder% 不存在！
    pause
    exit /b 1
)

echo 正在搜索AFS文件...
set "file_count=0"

:: 遍历所有AFS文件并解压
for %%f in ("%source_folder%\*.afs") do (
    if exist "%%f" (
        set /a file_count+=1
        echo.
        echo [处理 !file_count!] 正在解压: %%~nxf
        
        :: 为每个AFS文件创建单独的输出文件夹
        set "output_dir=%output_base%\%%~nf"
        if not exist "!output_dir!" mkdir "!output_dir!"
        
        :: 执行解压操作
        AFSPacker -e "%%f" "!output_dir!"
        
        if !errorlevel! equ 0 (
            echo ✓ 成功解压: %%~nxf
        ) else (
            echo ✗ 解压失败: %%~nxf
        )
    )
)

if %file_count% equ 0 (
    echo 在 %source_folder% 中未找到任何AFS文件！
) else (
    echo.
    echo ========================================
    echo 解压完成！共处理 %file_count% 个文件
    echo 输出目录: %output_base%
    echo ========================================
)

pause