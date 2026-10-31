"""Assemble le dossier source/ du submod « Traduction FR » pour le Submod Manager du launcher.

source/ reproduit l'arborescence de C:\\AgeoftheRing\\aotr ; le launcher la copie dans le jeu
au lancement et restaure les originaux à la fermeture.

Usage :
  python tools/build_submod.py --dest <dossier>            (ex. work/submod/source)
  python tools/build_submod.py --mod "Traduction FR"       (dossier du mod créé dans le launcher)
  options : --sans-audio
"""
import json
import os
import shutil
import sys

import audio_vf

ROOT = audio_vf.ROOT
MOD_MAPS = os.path.join(audio_vf.AOTR, 'aotr', 'maps')
LAUNCHER_MODS =os.path.join(os.environ.get('APPDATA', ''), 'Age of the Ring', 'Mods')


def launcher_source(display_name):
    with open(os.path.join(LAUNCHER_MODS, 'mods_manifest.json'), encoding='utf-8') as f:
        submods = json.load(f)['submods']
    for key, mod in submods.items():
        if display_name in (key, mod.get('display_name')):
            return os.path.join(LAUNCHER_MODS, key, mod['active_version'], 'source')
    sys.exit(f'Mod « {display_name} » introuvable : le créer d\'abord dans le launcher (Create Mod). '
             f'Mods existants : {", ".join(m.get("display_name", k) for k, m in submods.items())}')


def build(dest, audio=True):
    for sub in ('data', 'maps'):    # repartir propre (maps supprimées du mod, voix retirées…)
        shutil.rmtree(os.path.join(dest, sub), ignore_errors=True)
    os.makedirs(os.path.join(dest, 'data'), exist_ok=True)
    shutil.copy(os.path.join(ROOT, 'lotr.str'), os.path.join(dest, 'data', 'lotr.str'))
    maps = os.path.join(ROOT, 'maps', 'maps')
    for name in os.listdir(maps):
        src = os.path.join(maps, name, 'map.str')
        # seulement les maps dont le mod a encore un map.str (les autres ont été supprimées ou fusionnées)
        if os.path.exists(src) and os.path.exists(os.path.join(MOD_MAPS, name, 'map.str')):
            os.makedirs(os.path.join(dest, 'maps', name), exist_ok=True)
            shutil.copy(src, os.path.join(dest, 'maps', name, 'map.str'))
    print(f'texte : lotr.str + {len(os.listdir(os.path.join(dest, "maps")))} maps -> {dest}')
    if audio:
        games, mod = audio_vf.load()
        audio_vf.build(dest, games, mod, audio_vf.analyse(games, mod))


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--mod' in args:
        dest = launcher_source(args[args.index('--mod') + 1])
    elif '--dest' in args:
        dest = args[args.index('--dest') + 1]
    else:
        sys.exit(__doc__)
    build(dest, audio='--sans-audio' not in args)
