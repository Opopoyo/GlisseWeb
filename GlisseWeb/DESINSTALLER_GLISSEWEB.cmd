@echo off
chcp 65001 >nul
title GlisseWeb - Desinstallation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install\uninstall.ps1"
if errorlevel 1 pause
