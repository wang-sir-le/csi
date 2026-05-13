@echo off
echo Activating ESP-IDF environment...
call "C:\esp\v6.0\esp-idf\export.bat"

echo Running idf.py reconfigure with compile commands...
idf.py -DCMAKE_EXPORT_COMPILE_COMMANDS=ON reconfigure

if %ERRORLEVEL% EQU 0 (
    echo Checking for compile_commands.json...
    if exist "build\compile_commands.json" (
        echo Found compile_commands.json at build\compile_commands.json
        echo File size:
        dir "build\compile_commands.json"
    ) else (
        echo WARNING: compile_commands.json was not generated
        echo Listing build directory:
        dir build
    )
) else (
    echo idf.py reconfigure failed with error code %ERRORLEVEL%
    pause
)