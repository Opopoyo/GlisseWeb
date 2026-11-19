@echo off
setlocal
chcp 65001 >nul
title GlisseWeb - Installation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install\install.ps1"
if errorlevel 1 (
  echo.
  echo L'installation n'a pas abouti. Lire le message ci-dessus.
  pause
)
endlocal
