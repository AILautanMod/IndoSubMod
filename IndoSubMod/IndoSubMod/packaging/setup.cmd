@echo off
chcp 65001 >nul
title IndoSubMod Setup
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
exit /b %ERRORLEVEL%
