"""Paquet du submod « Traduction FR » du launcher : le dossier du submod (version active), son bloc de
mods_manifest.json, un Installer.bat (copie le dossier dans %APPDATA%\\Age of the Ring\\Mods et inscrit le submod dans
mods_manifest.json sans toucher aux autres) et un LISEZMOI.

Usage : python tools/paquet_test.py [sortie.zip] [--sans-audio] [--public] [--mod "Traduction FR"]
        par défaut work/Traduction_FR_AotR_test_<date>.zip (version de test, pour un testeur) ;
        --public : work/Traduction_FR_AotR_<version AotR>.zip, LISEZMOI pour les joueurs (téléchargement sur le site) ;
        --sans-audio : texte, cartes, écran de chargement et sous-titres seulement, sans !AotR_VF.big ni data/audio.

Le paquet complet contient des voix d'EA et le son des films.
"""
import datetime
import json
import os
import sys
import zipfile

from build_submod import LAUNCHER_MODS, ROOT

README = """Traduction FR d'Age of the Ring {version} - {title}{variant}

Installation (solo uniquement) :
1. Installer Age of the Ring {version}, le lancer une fois avec le launcher, puis fermer le launcher.
2. Extraire tout ce zip dans un dossier (clic droit > Extraire tout).
3. Double-cliquer sur Installer.bat (si Windows bloque : « Informations complémentaires » puis
   « Exécuter quand même »).
4. Ouvrir le launcher : onglet MODS > Installed Mods, vérifier que « {name} » est activé, puis jouer en solo.

Installation manuelle (si Installer.bat ne fonctionne pas) :
- copier le dossier « {key} » de ce zip dans %APPDATA%\\Age of the Ring\\Mods
  (Win+R, coller ce chemin, Entrée ; remplacer s'il existe déjà) ;
- dans ce dossier Mods, fichier mods_manifest.json : s'il n'existe pas ou ne contient aucun autre submod,
  copier celui du zip ; sinon l'ouvrir avec le Bloc-notes et ajouter le bloc "{key}" du zip dans "submods"
  (attention aux virgules entre les blocs).

Pour désinstaller : désactiver « {name} » dans le launcher, ou supprimer le dossier
%APPDATA%\\Age of the Ring\\Mods\\{key}.
{footer}"""

FOOTER_TEST = """
Merci de signaler : textes restés en anglais, MISSING: '...' à l'écran, fautes, sous-titres qui ne
correspondent pas à ce qui est dit (avec une capture d'écran et le nom de la mission).
Ce paquet contient des ressources d'EA et des films : ne pas le partager publiquement.
"""

FOOTER_PUBLIC = """
Un texte resté en anglais, un « MISSING: '...' » à l'écran, une faute, un sous-titre qui ne correspond pas
à ce qui est dit ? Signalez-le avec une capture d'écran et le nom de la mission : https://laterredumilieu.fr/mods/aotr
"""

INSTALLER_BAT = """@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
pause
"""

# Écrit en UTF-8 avec BOM : sinon PowerShell 5.1 lit le script en ANSI et casse les accents.
# mods_manifest.json réécrit en UTF-8 sans BOM (le launcher est en Python) ; copie de l'ancien à côté.
INSTALLER_PS1 = r"""param([string]$Mods = (Join-Path $env:APPDATA 'Age of the Ring\Mods'))
$ErrorActionPreference = 'Stop'
$key = '{key}'
Write-Host "Installation de « {name} » pour Age of the Ring"
if (Get-Process -Name 'AotR_Launcher' -ErrorAction SilentlyContinue) {{
    Write-Host "Fermez le launcher d'Age of the Ring, puis relancez Installer.bat."
    exit 1
}}
$src = Join-Path $PSScriptRoot $key
if (-not (Test-Path $src)) {{
    Write-Host "Dossier « $key » introuvable : extrayez tout le zip avant de lancer Installer.bat."
    exit 1
}}
if (-not (Test-Path $Mods)) {{ New-Item -ItemType Directory -Path $Mods | Out-Null }}
$dest = Join-Path $Mods $key
if (Test-Path $dest) {{ Remove-Item $dest -Recurse -Force }}
Write-Host "Copie des fichiers (cela peut prendre une minute)..."
Copy-Item $src $dest -Recurse

$block = (Get-Content (Join-Path $PSScriptRoot 'mods_manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json).submods.$key
$path = Join-Path $Mods 'mods_manifest.json'
if (Test-Path $path) {{
    $m = Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json
    Copy-Item $path "$path.avant_traduction" -Force
}} else {{
    $m = [pscustomobject]@{{ manifest_version = 1; last_game_version = ''; submods = [pscustomobject]@{{}} }}
}}
$old = $m.submods.PSObject.Properties[$key]
if ($old) {{
    $block.load_order = $old.Value.load_order
}} else {{
    $orders = @($m.submods.PSObject.Properties | ForEach-Object {{ [int]$_.Value.load_order }})
    $block.load_order = if ($orders.Count) {{ ($orders | Measure-Object -Maximum).Maximum + 1 }} else {{ 1 }}
}}
$block.enabled = $true
$m.submods | Add-Member -NotePropertyName $key -NotePropertyValue $block -Force
[IO.File]::WriteAllText($path, ($m | ConvertTo-Json -Depth 20), (New-Object System.Text.UTF8Encoding $false))
Write-Host "Terminé : « {name} » est installé et activé. Ouvrez le launcher et jouez en solo."
"""


def main():
    args = sys.argv[1:]
    no_audio = '--sans-audio' in args
    public = '--public' in args
    name = args[args.index('--mod') + 1] if '--mod' in args else 'Traduction FR'
    rest = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] != '--mod')]
    with open(os.path.join(LAUNCHER_MODS, 'mods_manifest.json'), encoding='utf-8') as f:
        manifest = json.load(f)
    key, mod = next((k, m) for k, m in manifest['submods'].items() if name in (k, m.get('display_name')))
    # seulement la version active : le dossier du submod contient aussi le zip de « Publish Submod »
    src = os.path.join(LAUNCHER_MODS, key, mod['active_version'])
    date = datetime.date.today()
    release = next((r for r in mod.get('releases', []) if r.get('version') == mod['active_version']), {})
    version = release.get('aotr_version') or manifest.get('last_game_version', '').removesuffix('.0') or '10.0'
    suffix = '_texte' if no_audio else ''
    out = rest[0] if rest else os.path.join(ROOT, 'work', f'Traduction_FR_AotR_{version}{suffix}.zip' if public
                                            else f'Traduction_FR_AotR_test_{date:%Y%m%d}{suffix}.zip')
    name = mod.get('display_name', key)
    files = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('LISEZMOI.txt', README.format(
            version=version, key=key, name=name,
            title=f'submod pour le launcher, version {mod["active_version"]}' if public
            else f'version de test du {date:%d/%m/%Y}',
            variant=' (textes seulement, sans les voix)' if no_audio else '',
            footer=FOOTER_PUBLIC if public else FOOTER_TEST).replace('\n', '\r\n'))
        z.writestr('Installer.bat', INSTALLER_BAT.replace('\n', '\r\n'))
        z.writestr('installer.ps1', '﻿' + INSTALLER_PS1.format(key=key, name=name).replace('\n', '\r\n'))
        z.writestr('mods_manifest.json', json.dumps({
            'manifest_version': manifest.get('manifest_version', 1),
            'last_game_version': manifest.get('last_game_version', ''),
            'submods': {key: mod}}, indent=4, ensure_ascii=False))
        for base, dirs, names in os.walk(src):
            rel = os.path.relpath(base, LAUNCHER_MODS).replace(os.sep, '/')
            for n in names:
                arc = f'{rel}/{n}'
                if no_audio and ('/data/audio/' in arc + '/' or n.lower().endswith('.big')):
                    continue
                # .big et sons déjà compressés ou peu compressibles : stockés tels quels (plus rapide)
                stored = n.lower().endswith(('.big', '.mp3'))
                z.write(os.path.join(base, n), arc, zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED)
                files += 1
    print(f'{files} fichiers -> {out} ({os.path.getsize(out) / 1e6:.0f} Mo)')


if __name__ == '__main__':
    main()
