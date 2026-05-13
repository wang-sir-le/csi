@echo off
echo Activating ESP-IDF environment...
call "C:\esp\v6.0\esp-idf\export.bat"
echo Building project...
idf.py build
if %ERRORLEVEL% EQU 0 (
    echo Build successful!
) else (
    echo Build failed with error code %ERRORLEVEL%
    pause
)