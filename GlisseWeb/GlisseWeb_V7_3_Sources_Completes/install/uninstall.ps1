#Requires -Version 5.1
$AppDir = Join-Path $env:LOCALAPPDATA "GlisseWeb"
Write-Host ""
Write-Host "Desinstallation de GlisseWeb" -ForegroundColor Cyan
Write-Host "Fermez toutes les fenetres GlisseWeb avant de continuer."
Write-Host "ATTENTION : les favoris, l'historique et les donnees des sites seront aussi supprimes."
$confirmation = Read-Host "Confirmer la suppression complete ? [O/N]"
if ($confirmation -notin @('O','o','oui','OUI','Oui')) { Write-Host 'Annule.'; exit 0 }
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$programs = [Environment]::GetFolderPath('Programs')
foreach ($shortcut in @((Join-Path $desktop 'GlisseWeb.lnk'), (Join-Path $programs 'GlisseWeb.lnk'), (Join-Path $programs 'Desinstaller GlisseWeb.lnk'))) {
    Remove-Item -LiteralPath $shortcut -Force -ErrorAction SilentlyContinue
}
try {
    Remove-Item -LiteralPath $AppDir -Recurse -Force -ErrorAction Stop
    Write-Host 'GlisseWeb a ete desinstalle.' -ForegroundColor Green
} catch {
    Write-Host "Certaines donnees ne peuvent pas etre supprimees (le programme est peut-etre ouvert)." -ForegroundColor Yellow
    Write-Host $_.Exception.Message
}
Read-Host 'Appuyez sur Entree pour fermer'
