@echo off
setlocal enabledelayedexpansion
title SpaceRouge - Android build
echo.
echo  SpaceRouge Android build (uses WSL / Ubuntu)
echo  -------------------------------------------
echo.

where wsl >nul 2>nul
if errorlevel 1 goto nowsl

rem Use an Ubuntu distro explicitly - the default WSL distro may be something
rem else (e.g. docker-desktop) that has no sudo / apt.
set "DISTRO="
for %%d in (Ubuntu Ubuntu-24.04 Ubuntu-22.04 Ubuntu-20.04 Debian) do (
    if not defined DISTRO (
        wsl -d %%d -e true >nul 2>nul
        if not errorlevel 1 set "DISTRO=%%d"
    )
)
if not defined DISTRO goto noubuntu
echo  Using WSL distro: %DISTRO%
echo.

rem Folder of this script, without the trailing backslash
set "HERE=%~dp0"
set "HERE=%HERE:~0,-1%"

rem Convert it to a WSL path (C:\Users\... -> /mnt/c/Users/...)
for /f "usebackq delims=" %%p in (`wsl -d %DISTRO% wslpath -a "%HERE%"`) do set "WSLHERE=%%p"

wsl -d %DISTRO% bash "%WSLHERE%/tools/wsl_build.sh" "%WSLHERE%"
if errorlevel 1 (
    echo.
    echo  Build failed - scroll up for the error.
    pause
    exit /b 1
)
echo.
echo  APK is in: %HERE%\bin
echo  Copy it to your phone and open it, or run:  adb install -r bin\^<name^>.apk
explorer "%HERE%\bin"
pause
exit /b 0

:noubuntu
echo  WSL is installed, but there's no Ubuntu distro in it.
echo  (Your default WSL Linux can't run the Android build tools.)
echo.
echo  1. Open PowerShell as Administrator and run:   wsl --install -d Ubuntu
echo  2. When Ubuntu opens, pick a username and password, then close it.
echo  3. Double-click build_apk.bat again.
echo.
echo  Installed distros:
wsl -l -v
echo.
pause
exit /b 1

:nowsl
echo  WSL (Windows Subsystem for Linux) isn't set up yet.
echo.
echo  1. Open PowerShell as Administrator and run:   wsl --install -d Ubuntu
echo  2. Restart the laptop.
echo  3. Ubuntu opens by itself - pick a username and password.
echo  4. Double-click build_apk.bat again.
echo.
pause
exit /b 1
