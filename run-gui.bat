@echo off
setlocal
cd /d "%~dp0"
echo Launching Langton's Ant Simulator GUI...
python gui.py
if errorlevel 1 (
    echo ERROR: Failed to launch GUI. Make sure Python is in PATH.
    pause
)
