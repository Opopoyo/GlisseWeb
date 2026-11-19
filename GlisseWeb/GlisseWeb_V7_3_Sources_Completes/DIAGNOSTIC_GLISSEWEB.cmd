@echo off
setlocal
chcp 65001 >nul
title GlisseWeb V7 - Diagnostic
set "APPDIR=%LOCALAPPDATA%\GlisseWeb"
if not exist "%APPDIR%\.venv\Scripts\python.exe" (
  echo GlisseWeb non installe. Lancer INSTALLER_GLISSEWEB.cmd.
  pause
  exit /b 1
)
echo Version Python et Qt WebEngine installees :
"%APPDIR%\.venv\Scripts\python.exe" -c "import sys, PySide6; print(sys.version); print('PySide6', PySide6.__version__)"
echo.
echo Lancement de GlisseWeb avec erreurs visibles. Fermer la fenetre pour quitter.
"%APPDIR%\.venv\Scripts\python.exe" "%APPDIR%\main.py"
echo.
echo Fin de GlisseWeb. Code de retour: %errorlevel%
pause
endlocal
