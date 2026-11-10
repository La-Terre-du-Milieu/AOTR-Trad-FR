"""Paquet à envoyer à un testeur : le submod « Traduction FR » du launcher, zippé avec son bloc de mods_manifest.json
et un LISEZMOI d'installation.

Usage : python tools/paquet_test.py [sortie.zip] [--sans-audio] [--mod "Traduction FR"]
        (par défaut work/Traduction_FR_AotR_test_<date>.zip ; --sans-audio : texte, cartes, écran de chargement et
        sous-titres seulement, sans !AotR_VF.big ni data/audio — beaucoup plus léger, pour tester les textes)

Le paquet contient des voix d'EA et le son des films : à envoyer en privé à un testeur, pas à publier.
"""
import datetime
import json
import os
import sys
import zipfile

from build_submod import LAUNCHER_MODS, ROOT

README = """Traduction FR d'Age of the Ring {version} - version de test du {date}{variant}

Installation (solo uniquement) :
1. Installer Age of the Ring {version} avec le launcher, le lancer une fois, puis le fermer.
2. Ouvrir le dossier %APPDATA%\\Age of the Ring\\Mods (Win+R, coller ce chemin, Entrée).
3. Copier le dossier « {key} » de ce zip dans Mods (remplacer s'il existe déjà).
4. Fichier mods_manifest.json de ce dossier Mods :
   - s'il n'existe pas, ou s'il ne contient aucun autre submod : copier celui du zip ;
   - sinon : l'ouvrir avec le Bloc-notes et ajouter le bloc "{key}" du zip dans "submods"
     (attention aux virgules entre les blocs).
5. Relancer le launcher, vérifier que « {name} » est activé dans le Submod Manager, jouer en solo.

Pour désinstaller : désactiver le submod dans le Submod Manager (ou supprimer le dossier « {key} »).

Merci de signaler : textes restés en anglais, MISSING: '...' à l'écran, fautes, sous-titres qui ne
correspondent pas à ce qui est dit (avec une capture d'écran et le nom de la mission).
Ce paquet contient des ressources d'EA et des films : ne pas le partager publiquement.
"""


def main():
    args = sys.argv[1:]
    no_audio = '--sans-audio' in args
    name = args[args.index('--mod') + 1] if '--mod' in args else 'Traduction FR'
    rest = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] != '--mod')]
    with open(os.path.join(LAUNCHER_MODS, 'mods_manifest.json'), encoding='utf-8') as f:
        manifest = json.load(f)
    key, mod = next((k, m) for k, m in manifest['submods'].items() if name in (k, m.get('display_name')))
    src = os.path.join(LAUNCHER_MODS, key)
    date = datetime.date.today()
    out = rest[0] if rest else os.path.join(ROOT, 'work', f'Traduction_FR_AotR_test_{date:%Y%m%d}'
                                              f'{"_texte" if no_audio else ""}.zip')
    version = manifest.get('last_game_version', '').rsplit('.0', 1)[0] or '10.0'
    files = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr('LISEZMOI.txt', README.format(
            version=version, date=f'{date:%d/%m/%Y}', key=key, name=mod.get('display_name', key),
            variant=' (textes seulement, sans les voix)' if no_audio else '').replace('\n', '\r\n'))
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
