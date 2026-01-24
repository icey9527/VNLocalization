@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo          AFS文件批量打包工具
echo ========================================

:: 设置包含解压文件夹的目录
set "source_folder=.\new"
:: 设置输出AFS文件的文件夹
set "output_folder=.\packed_afs"

:: 创建输出文件夹
if not exist "%output_folder%" mkdir "%output_folder%"

:: 检查源文件夹是否存在
if not exist "%source_folder%" (
    echo 错误：源文件夹 %source_folder% 不存在！
    pause
    exit /b 1
)

echo 正在搜索可打包的文件夹...
set "folder_count=0"

:: 遍历源文件夹中的所有子文件夹
for /d %%d in ("%source_folder%\*") do (
    set /a folder_count+=1
    echo.
    echo [处理 !folder_count!] 正在打包: %%~nxd
    
    :: 设置输出AFS文件路径
    set "output_file=%output_folder%\%%~nxd.afs"
    
    :: 执行打包操作
    AFSPacker -c "%%d" "!output_file!"
    
    if !errorlevel! equ 0 (
        echo ✓ 成功打包: %%~nxd.afs
    ) else (
        echo ✗ 打包失败: %%~nxd
    )
)

if %folder_count% equ 0 (
    echo 在 %source_folder% 中未找到任何可打包的文件夹！
) else (
    echo.
    echo ========================================
    echo 打包完成！共处理 %folder_count% 个文件夹
    echo 输出目录: %output_folder%
    echo ========================================
)

pause