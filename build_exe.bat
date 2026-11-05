@echo off
rem Builds the Windows version of SpaceRouge into dist\SpaceRouge\
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail
python -m PyInstaller --noconfirm --clean SpaceRouge.spec
if errorlevel 1 goto :fail
echo.
echo Done: dist\SpaceRouge\SpaceRouge.exe
echo Zip the whole dist\SpaceRouge folder to share the game.
pause
exit /b 0
:fail
echo.
echo Build failed - see the messages above.
pause
exit /b 1
