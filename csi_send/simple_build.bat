@echo off
echo === 简单构建测试 ===
echo 1. 激活ESP-IDF环境
call "C:\esp\v6.0\esp-idf\export.bat"

echo.
echo 2. 运行idf.py build
idf.py build

echo.
if %ERRORLEVEL% EQU 0 (
    echo === 构建成功 ===
    echo 生成的文件:
    dir build\*.bin
) else (
    echo === 构建失败，错误码: %ERRORLEVEL% ===
    pause
)