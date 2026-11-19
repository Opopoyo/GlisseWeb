#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$AppName = "GlisseWeb"
$AppDir = Join-Path $env:LOCALAPPDATA $AppName
$SourceDir = Join-Path (Split-Path -Parent $PSScriptRoot) "GlisseWeb"
$VenvDir = Join-Path $AppDir ".venv"
$PythonInVenv = Join-Path $VenvDir "Scripts\python.exe"
$PythonwInVenv = Join-Path $VenvDir "Scripts\pythonw.exe"

function Get-SuitablePython {
    $versions = @("-3.13", "-3.12", "-3.11")
    $pyCmd = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($pyCmd) {
        foreach ($version in $versions) {
            try {
                $candidate = & $pyCmd.Source $version -c 'import sys,struct; print(sys.executable if (3,11) <= sys.version_info[:2] <= (3,13) and struct.calcsize("P") == 8 else "")' 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) {
                    return $candidate.Trim()
                }
            } catch { }
        }
    }
    $pythonCmd = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        try {
            $candidate = & $pythonCmd.Source -c 'import sys,struct; print(sys.executable if (3,11) <= sys.version_info[:2] <= (3,13) and struct.calcsize("P") == 8 else "")' 2>$null
            if ($LASTEXITCODE -eq 0 -and $candidate -and (Test-Path $candidate.Trim())) {
                return $candidate.Trim()
            }
        } catch { }
    }
    foreach ($runtime in @('Python313\python.exe', 'Python312\python.exe')) {
        $localPython = Join-Path $AppDir $runtime
        if (Test-Path $localPython) { return $localPython }
    }
    return $null
}

try {
    Write-Host ""
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host "        GLISSEWEB V7.3 - INSTALLATION WINDOWS" -ForegroundColor Cyan
    Write-Host "===============================================" -ForegroundColor Cyan
    Write-Host ""
    if (-not [Environment]::Is64BitOperatingSystem) {
        throw "GlisseWeb necessite Windows 64 bits."
    }
    if (-not (Test-Path (Join-Path $SourceDir "main.py"))) {
        throw "Dossier GlisseWeb introuvable. Extraire d'abord le ZIP entier."
    }
    New-Item -ItemType Directory -Path $AppDir -Force | Out-Null
    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $AppDir -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall.ps1") -Destination (Join-Path $AppDir "uninstall.ps1") -Force

    $Python = Get-SuitablePython
    if (-not $Python) {
        Write-Host "[1/4] Installation de Python 3.13 dans le dossier GlisseWeb..." -ForegroundColor Yellow
        # Source officielle Python.org. Installation locale sans droits administrateur.
        $Installer = Join-Path $env:TEMP "GlisseWeb-python-3.13.17-amd64.exe"
        $PythonDir = Join-Path $AppDir "Python313"
        $url = "https://www.python.org/ftp/python/3.13.17/python-3.13.17-amd64.exe"
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $Installer
        # SHA-256 publie par python.org pour l'installateur Windows x64 3.13.17.
        $expectedSha256 = '5da012101ba2e17113a9a1cd901e9ce1441086f2b7ecb5de06ec94163899a190'
        $actualSha256 = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualSha256 -ne $expectedSha256) {
            Remove-Item -LiteralPath $Installer -Force -ErrorAction SilentlyContinue
            throw 'Verification cryptographique du programme Python echouee. Installation annulee.'
        }
        $args = @("/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0", "Include_test=0", "TargetDir=`"$PythonDir`"")
        $p = Start-Process -FilePath $Installer -ArgumentList $args -PassThru -Wait
        if ($p.ExitCode -ne 0) { throw "Installation Python echouee (code $($p.ExitCode))." }
        $Python = Join-Path $PythonDir "python.exe"
        if (-not (Test-Path $Python)) { throw "Python introuvable apres installation." }
        Remove-Item -LiteralPath $Installer -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "[1/4] Python detecte : $Python" -ForegroundColor Green
    }

    Write-Host "[2/4] Preparation de l'environnement..." -ForegroundColor Cyan
    if (-not (Test-Path $PythonInVenv)) {
        & $Python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "Impossible de creer l'environnement Python." }
    }
    if (-not (Test-Path $PythonInVenv)) { throw "Python virtuel introuvable." }

    Write-Host "[3/4] Installation du moteur web Qt / Chromium..." -ForegroundColor Cyan
    Write-Host "Une connexion Internet est necessaire : plusieurs centaines de Mo peuvent etre telecharges."
    & $PythonInVenv -m pip --isolated install --disable-pip-version-check --only-binary=:all: --index-url https://pypi.org/simple -r (Join-Path $AppDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Echec de l'installation des bibliotheques PySide6." }
    & $PythonInVenv -c "from PySide6.QtWebEngineWidgets import QWebEngineView; print('Moteur web installe : OK')"
    if ($LASTEXITCODE -ne 0) { throw "Le moteur web ne peut pas etre importe." }

    Write-Host "[4/4] Creation des raccourcis..." -ForegroundColor Cyan
    $Icon = Join-Path $AppDir "glisseweb.ico"
    $MainScript = Join-Path $AppDir "main.py"
    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('DesktopDirectory')
    $programs = [Environment]::GetFolderPath('Programs')
    foreach ($shortcutPath in @((Join-Path $desktop "GlisseWeb.lnk"), (Join-Path $programs "GlisseWeb.lnk"))) {
        $link = $shell.CreateShortcut($shortcutPath)
        $link.TargetPath = $PythonwInVenv
        $link.Arguments = "`"$MainScript`""
        $link.WorkingDirectory = $AppDir
        $link.Description = "GlisseWeb - navigateur plein ecran a barre laterale"
        if (Test-Path $Icon) { $link.IconLocation = $Icon }
        $link.Save()
    }
    $removalShortcut = Join-Path $programs "Desinstaller GlisseWeb.lnk"
    $link = $shell.CreateShortcut($removalShortcut)
    $link.TargetPath = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
    $link.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $AppDir 'uninstall.ps1')`""
    $link.WorkingDirectory = $env:TEMP
    $link.Description = "Desinstaller GlisseWeb et supprimer ses fichiers"
    $link.Save()

    Write-Host ""
    Write-Host "INSTALLATION TERMINEE !" -ForegroundColor Green
    Write-Host "Un raccourci GlisseWeb a ete ajoute au Bureau et au menu Demarrer."
    Write-Host "Profil, favoris et historique V1 conserves si deja installes."
    Write-Host "Lancement du navigateur..."
    Start-Process -FilePath $PythonwInVenv -ArgumentList "`"$MainScript`"" -WorkingDirectory $AppDir
    exit 0
} catch {
    Write-Host ""
    Write-Host "ERREUR : $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Verifier Internet, l'espace disque et les droits d'installation Windows."
    exit 1
}
